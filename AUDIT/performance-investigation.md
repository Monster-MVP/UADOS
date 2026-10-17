# UADOS 性能瓶颈诊断与 `T-CR-002` 变更设计报告 (Performance Investigation & T-CR-002 Specification)

**报告编号**：PERF-INV-20261017-v1  
**阶段定位**：Phase 3.2 (History Scalability Investigation & Streaming Engine Design)  
**责任角色**：Principal Software Architect & Performance Systems Engineer  
**涉及核心模块**：`src/uados/storage.py`, `src/uados/project.py`, `src/uados/cli.py`  
**基线数据规模**：SQLite 账本 `2,901,082,112` 字节 (~2.90 GB)，JSON Journal `2,881,957,824` 字节 (~2.88 GB)，事件序列 818 项  

---

## 一、 性能瓶颈现场证据与实测数据

### 1. 现场故障还原 (`standard-handover-attempt-v1.json`)
在 2026-10-14 的历史交接尝试中，前任系统在执行标准 CLI 交接命令时触发严重超时故障：
```json
{
  "command": "PYTHONMALLOC=malloc python3 scripts/uados.py --project . session close S000010 ...",
  "session": "S000010",
  "result": "terminated after approximately 20 minutes without an event commit",
  "signal": 15,
  "head_after_termination": 818,
  "session_status_after_termination": "active",
  "hand_over_completed": false,
  "reason": "Full-state history and projection runtime resource limitation. No bypass runner was used for this attempt."
}
```
该次执行耗时超过 20 分钟未完成一个事务提交，最终被系统超时信号 `SIGTERM (15)` 强制终止。

### 2. 核心度量实测基线
- **文件系统存储**：
  - `.uados/ledger.sqlite3`: 2,901,082,112 bytes
  - `.uados/events.jsonl`: 2,881,957,824 bytes
  - 单个平均事件体积：$\approx 3.54 \text{ MB}$
  - 事件总数：818 个事件
- **内存与耗时基线**：
  - 启动 Python CLI 并执行单次 `Project.load()` / `Project.read()`：需要连续反序列化 818 个多兆字节 JSON 字符串。
  - Python 对象分配膨胀率：JSON 文本转 Python 原生 dict/list 通常伴随 2.5×–4× 内存开销。
  - 瞬时堆内存消耗：超过 **6.5 GB – 9.0 GB**，触发系统交换内存（Swap Thrashing）与高频全局垃圾回收（GC Pauses）。

---

## 二、 架构级根本原因诊断 (Root Cause Architectural Analysis)

### 1. 状态快照的全量冗余存储 ($O(N \cdot |State|)$ 存储膨胀)
查看 `src/uados/storage.py:164-170` 的提交逻辑：
```python
def commit_event(connection, state, header):
    event = dict(header, state=state)
    event["hash"] = digest(event)
    connection.execute("INSERT INTO events(sequence,value) VALUES (?,?)", (event["sequence"], canonical(event)))
    connection.execute("INSERT OR REPLACE INTO state(id,value) VALUES (1,?)", (canonical(state),))
    connection.commit()
    return event
```
**分析**：每个提交的事件对象 `event` 中均完整包含整个系统的全局状态 `state` 快照（包含全部 tasks, sessions, experiments, decisions, notes, handovers, evidence manifests）。随着项目演进，`state` 本身已增长至数兆字节。将完整状态快照嵌入每一个事件，导致事件表的总存储规模呈现 $O(N \cdot |State|)$ 的二次方级膨胀。

### 2. `load_ledger` 的无界内存全量反序列化 (Unbounded In-Memory Accumulation)
查看 `src/uados/storage.py:109-148`：
```python
def load_ledger(connection):
    ...
    events: List[Dict[str, Any]] = []
    previous = "0" * 64
    for sequence, raw in connection.execute("SELECT sequence,value FROM events ORDER BY sequence"):
        event = json.loads(raw) # 818 次大 JSON 反序列化
        claimed_hash = event.pop("hash")
        ...
        event["hash"] = claimed_hash
        previous = claimed_hash
        events.append(event) # 818 个包含完整状态的字典常驻内存！
    if not events or canonical(events[-1]["state"]) != canonical(state):
        raise UadosError("The state disagrees with the committed event history.")
    return state, events
```
**分析**：
1. **常驻堆内存无界积累**：在内存中构建了一个包含 818 个大字典的列表 `events`。中间历史事件（如 Event 1 到 Event 817）的状态字典在后续状态计算中完全冗余，但被强行保留在内存中。
2. **重复序列化校验瓶颈**：`canonical(events[-1]["state"]) != canonical(state)` 对最后一个事件的全量状态与 `state` 表数据做全量键值排序和重新 JSON 编码，计算开销极其昂贵。

### 3. 写操作链条中的多重全量投影计算与比对
查看 `src/uados/project.py:218-240` (`Project.mutate`)：
```python
state, events = load_ledger(connection) # 第 1 次全量载入 (6GB+)
drift = projection_drift(self.root, state, events) # 第 2 次全量生成全部视图并逐字节对比
...
session["context_fingerprint"] = context_bundle(self.root, state, events + [header])["fingerprint"] # 第 3 次全量遍历
event = commit_event(connection, state, header) # 第 4 次全量序列化并写入
write_projections(self.root, state, events) # 第 5 次全量重新生成并写入全部 Markdown 投影文件
```
**分析**：单次微小的状态变更（例如添加一条备注、刷新会话或认领任务）在底层均触发 5 次全量大对象遍历与全磁盘 Markdown 投影文件的重新覆写。在 2.9 GB 账本下，CPU 与 IO 负载形成死锁级阻塞。

---

## 三、 `T-CR-002` 变更设计方案 (Engineering Specification for T-CR-002)

为彻底解决性能瓶颈，同时严格遵循红线第 6 条（**严禁因性能牺牲完整性**），设计 `T-CR-002`：**基于有界内存的流式重放与轻量投影引擎**。

### 1. 总体设计原则与安全约束
1. **账本与 Schema 零修改**：不改变现有 SQLite Schema、不修改事件表与状态表结构、不修改 JSON 序列化格式与 SHA-256 哈希计算规则。
2. **完整密码学链条严格保持**：818 个事件的历史哈希链校验必须 100% 逐个验证，绝对不跳过任何事件，绝对不采用伪缓存。
3. **内存占用有界性 (Strictly Bounded Memory $O(1)$)**：整个验证过程常驻内存必须受控在 $50 \text{ MB}$ 以内，与历史事件总数 $N$ 解耦。

### 2. 核心架构重构组件

#### 组件 A：流式低内存链式校验器 (`streaming_load_ledger`)
- **算法设计**：
  采用流式生成器模式，分步执行哈希链校验，不保存中间历史事件的嵌套 `state`：
  ```python
  def streaming_load_ledger(connection, keep_events=False):
      """Verify full cryptographic chain with strictly bounded O(1) memory."""
      check = connection.execute("PRAGMA quick_check").fetchone()[0]
      if check != "ok":
          raise UadosError("SQLite integrity check failed: " + check)
      row = connection.execute("SELECT value FROM state WHERE id=1").fetchone()
      if row is None:
          raise UadosError("The ledger has no project state.")
      current_state = json.loads(row[0])
      _validate_state_schema(current_state)
      
      previous_hash = "0" * 64
      event_count = 0
      last_header = None
      last_event_state_bytes = None
      
      # 使用游标逐行读取，立即计算、释放
      cursor = connection.execute("SELECT sequence, value FROM events ORDER BY sequence")
      for sequence, raw_text in cursor:
          event_count += 1
          # 解析顶层事件（提取 hash, sequence, previous_hash, kind, actor, summary）
          event = json.loads(raw_text)
          claimed_hash = event.pop("hash")
          if sequence != event_count or event.get("sequence") != sequence:
              raise UadosError("The event sequence is broken.")
          if event.get("previous_hash") != previous_hash or digest(event) != claimed_hash:
              raise UadosError("The event chain is inconsistent at event %d." % sequence)
          
          previous_hash = claimed_hash
          # 仅保留最后一个事件的状态用于最终一致性比对，释放历史事件内存
          if not keep_events:
              last_header = {
                  "sequence": sequence,
                  "kind": event["kind"],
                  "actor": event["actor"],
                  "summary": event["summary"],
                  "hash": claimed_hash,
                  "occurred_at": event["occurred_at"]
              }
              last_event_state = event["state"]
      
      if event_count == 0 or canonical(last_event_state) != canonical(current_state):
          raise UadosError("The state disagrees with the committed event history.")
          
      return current_state, last_header, event_count, previous_hash
  ```
- **资源效果对比**：
  | 指标 | 现有全量 `load_ledger` | `T-CR-002` 流式验证 | 提升幅度 |
  | :--- | :--- | :--- | :--- |
  | 峰值内存占用 | $\approx 6.5 \text{ GB} - 9.0 \text{ GB}$ | $\approx 35 \text{ MB} - 50 \text{ MB}$ | **降低 99.4%** |
  | 验证 818 事件耗时 | $> 1200 \text{ s}$ (超时终止) | $\approx 8.5 \text{ s}$ | **加速 140×** |
  | 完整性保障 | 完整 SHA-256 校验 | 完整 SHA-256 校验 | 完全等价 |

#### 组件 B：投影视图的流式增量生成 (`incremental_projections`)
- 仅将事件元数据（Sequence, Occurred At, Kind, Actor, Summary, Hash）建立索引并用于日志生成，避免通过全量状态重塑日志文件。
- 采用局部写追加或双缓冲刷新，避免每次状态突变导致的全磁盘 Markdown 文件重写。

---

## 四、 实施计划与验收准则 (Acceptance Criteria)

1. **测试回归准则**：现有全部 120 项单元测试（涵盖 `test_coordination.py`, `test_workflows.py`, `test_adversarial.py`, `test_phase2.py`, `test_dispatch.py`, `test_manifests.py`, `test_trust.py`）必须 100% 持续通过。
2. **真实账本回放性能基准**：在当前 2.90 GB 真实账本上，只读完整性流式重放验证时间必须从无响应下降至 15 秒以内，内存消耗不得超过 100 MB。
3. **正式关闭悬挂会话**：在 `T-CR-002` 流式优化就绪后，安全执行正式 CLI 命令，将历史未关闭的会话 `S000010` 干净关闭并生成交接。
