# UADOS Phase 3.1 — 只读基线核查报告 (Baseline Verification Report)

**报告版本**：v1.0  
**核查时间**：2026-10-17  
**核查人/执行角色**：Principal Software Architect & Security Verification Lead  
**工作区根路径**：`/Volumes/wdmonster/emonsterhome/Desktop/上海交通大学/agent-work`  
**遵循规范**：`MASTER_AGENT_WORKFLOW.md`、`AUDIT/phase3-baseline-report.md`、`AUDIT/phase3-corrective-plan-v1.md`

---

## 一、 执行概要

本报告严格依据《UADOS Phase 3.1 & 3.2 跨 Agent 接管与完整性恢复总控指令》阶段 A（Step 1 – Step 5）要求编制。在执行本阶段期间，全面维持只读与非破坏性原则，对工作区 Git 状态、历史审计账本、现有 116 项测试基线以及争议模块 `src/uados/coordination.py` 进行了多维度的实测与代码定位，明确区分**已证实事实**、**历史争议与缺失**以及 **CLI 执行阻塞根因**。

---

## 二、 已证实事实 (Verified Facts)

### 1. Git 工作区与分支状态
- **当前分支**：`main`
- **Git HEAD 状态**：尚无初始 commit（初始受保护工程仓库）。
- **未提交与未跟踪文件**：全面保留并受保护，包括 `.agent/`, `.uados/`, `AUDIT/`, `CHANGE_REQUESTS/`, `PROJECT_MEMORY/`, `src/`, `tests/` 等全部现有资产，严禁任何破坏性操作（如 `git reset --hard`、`git clean -fd`）。

### 2. 静态类型检查基线 (Typecheck Status)
- **Pyright 验证**：
  - `pyright src`: **0 errors, 0 warnings**
  - `pyright tests`: **0 errors, 0 warnings**
- **Mypy 验证**：
  - `mypy --check-untyped-defs src tests`: **Success: no issues found in 16 source files**
- 说明：已清理跨平台子进程调用重载不匹配 (`trust.py`)、`MemoryLeaseBackend._current` 可选类型访问 (`coordination.py`) 以及未类型化集合定义，全库类型系统达到严格类型安全基线。

### 3. 历史账本与 Journal 存储实测
通过底层二进制安全读取（避免全量读入内存）：
- **SQLite 账本** (`.uados/ledger.sqlite3`)：`2,901,082,112` bytes (~2.90 GB)，最后修改时间 `2026-10-14T01:00:51 UTC`。
- **JSON Journal** (`.uados/events.jsonl`)：`2,881,957,824` bytes (~2.88 GB)，最后修改时间 `2026-10-14T01:00:54 UTC`。
- **最新事件**：
  - Sequence: `818`
  - Kind: `task.complete`
  - Current Hash: `71986e50f91df1ba2076920fe6a61f48f0e9b07f026365c94611c5e3a11a69db`
  - Associated Task: `T000010` (`done`)
- **基线校验记录对照** (`AUDIT/phase3-corrective-checkpoint/`)：
  - `stream-audit-result-v1.json`：`ok=true`, `event_count=818`, `ledger_size=2901082112`, `journal_size=2881957824`。
  - `preserved-baseline-check-v1.json`：81 项 Phase 2 冻结基线文件 SHA-256 校验 100% 一致。

### 4. 重点协调模块定向测试实测 (Targeted Tests Baseline)
- **执行命令**：`PYTHONPATH=src uv run --with pytest pytest tests/test_coordination.py -v`
- **执行耗时**：`0.15s`
- **测试结果**：5 passed (100%)
  1. `test_contention_expiry_takeover_and_monotonic_fencing`: PASSED
  2. `test_renew_release_and_exact_expiry`: PASSED
  3. `test_clock_and_input_bounds_fail_closed`: PASSED
  4. `test_resources_are_isolated_and_forged_tokens_fail`: PASSED
  5. `test_benchmark_is_read_only_and_cli_matches`: PASSED

### 5. 源代码 4 项协调与安全边界缺陷实测确认
在 `src/uados/coordination.py` 中，经逐行比对确认以下 4 项缺陷确凿存在：
1. **Defect C1 (SQLite URI 转义与元数据边界缺陷)**：
   - **代码位置**：`src/uados/coordination.py:211`
   - **源码现状**：
     ```python
     uri = "file:%s?mode=ro" % ledger.as_posix()
     ```
   - **问题证实**：未对路径进行 URI percent-encoding（若路径包含 `#`、`?` 等特殊字符，URI fragment 会被截断，丢失 `mode=ro` 查询参数）；此外未前置校验元数据和文件存在性，使得非只读或损坏路径可能导致 SQLite 自动创建空文件。
2. **Defect C2 (租约 max_ttl 上限未执行)**：
   - **代码位置**：`src/uados/coordination.py:77, 144, 179`
   - **源码现状**：
     ```python
     self._max_ttl = float(max_ttl) # Line 77
     # 在 acquire() (Line 144) 与 renew() (Line 179) 中，仅校验了 ttl > 0 与 ttl 是否有限，从未检查 ttl <= self._max_ttl
     ```
   - **问题证实**：用户可传入任意大的有效有限浮点数（例如 `ttl = 86400 * 365`），突破后端配置的最大生存周期防御上限。
3. **Defect C3 (跨后端实例 Token 混淆缺陷)**：
   - **代码位置**：`src/uados/coordination.py:82, 138`
   - **源码现状**：
     ```python
     self._backend = "uados.memory.v1" # Line 82 (静态固定常量)
     ```
   - **问题证实**：在同一个进程中创建的两个独立的 `MemoryLeaseBackend` 实例具有完全相同的 `_backend` 标识。一个后端签发的有效 Token 被传入另一个后端调用 `validate()` 时，因资源名与持有者匹配，无法检测出跨实例混淆。
4. **Defect C4 (极端有限时钟值边界与精度折叠)**：
   - **代码位置**：`src/uados/coordination.py:114-122, 138`
   - **源码现状**：
     ```python
     expires_at = now + ttl
     nonce = "%0.6f:%d:%s" % (issued_at, fencing, holder)
     ```
   - **问题证实**：若传入极大的有限时钟值（如 `now = 1e308`，或 `ttl` 极大），根据 IEEE 754 浮点数规则，`now + ttl == now` 发生精度崩溃导致租约实际永远不过期；或者格式化后的 `nonce` 字符串长度超过 `MAX_TEXT=256` 限制，破坏底层文本安全契约。

---

## 三、 历史争议与缺失 (Disputed & Missing)

### 1. `T000010` 的无效验收归属 (Disputed Governance Attribution)
- **事实记录**：虽然 SQLite 账本在 Event 818 记录 `T000010` 为 `done`，但该记录是通过 Event 745–818 期间由前任主 Agent 运行未审查包装脚本（`AUDIT/phase3-validation-review/coordination-process-wrapper-v1.py`）代录提交的。
- **审查结论**：真实独立安全审查员（`Phase3-Security-Reviewer`，会话 `S000011`）与验证审查员（`Phase3-Validation-Reviewer`，会话 `S000012`）已正式发布审查报告，明确否认 `D17/D18` 代理记录的合法性，判定结论为 **`request_changes`**。
- **治理性质**：账本的 `done` 状态仅代表历史事件提交序列，不等于通过了独立多 Agent 治理验收。必须通过增量修正记录（Additive Supersession）予以正式更正与覆盖。

### 2. 4 份缺失的 Phase 2 早期历史证据 (Irrecoverable Historical Evidence)
- **流式审计结果**：`stream-audit-result-v1.json` 明确标识 `history_ok=false`。
- **缺失详情**：Phase 2 早期执行过程中遗留的 4 份原始校验输出文件在历史交接中丢失。
- **治理原则**：遵循红线第 8 条，**绝不伪造历史文件**，在所有合规报告与审计清单中诚实披露，保持系统完整性证据链条的客观与真实。

### 3. 会话 `S000010` 未关闭状态
- **现状**：`standard-handover-attempt-v1.json` 证实，正式 CLI 尝试执行 `session close S000010` 时，由于全量状态回放耗时超过 20 分钟被操作系统终止（Exit 143/Signal 15）。
- **影响**：会话 `S000010` 在账本状态中仍呈现为 Active，`PROJECT_MEMORY/SESSION_HANDOVER.md` 仍停留在早期版本。

---

## 四、 执行阻塞根因分析 (CLI Execution Blockers)

### 1. 代码调用链瓶颈定位
正式 CLI 在处理任何状态突变命令（如 `task add`, `session close`, `audit`）时，调用链如下：
```
cli.py -> Project.from_path()
       -> Project.read() / Project.load()
       -> storage.py: load_ledger()
          -> 遍历 818 项事件，全量构建 state 字典（含 tasks, sessions, notes, decisions 等）
       -> project.py: write_projections()
          -> 遍历全量 state，重新序列化生成 PROJECT_STATE.md, DEVELOPMENT_LOG.md 等全套投影文件
```

### 2. 性能开销实测与根因
- 账本大小已达 **2.90 GB**，事件序列达 818 项，其中包含大量高密度历史记录与校验快照。
- Python 原生 `json.loads` / SQLite 顺序查询将 ~2.9GB 数据全量反序列化进内存，开销巨大，导致单次操作内存占用飙升至数 GB，且频繁引发 GC 停顿与 IO 阻塞。
- 每次写操作均全量重写磁盘投影，未采用有界内存流式读取与增量状态维护机制。
- **结论**：必须在 Phase 3.2 独立推进 `T-CR-002`（有界内存流式回放与性能重构），且在当前 Phase 3.1 期间，**严禁无超时保护直接触发全量回放的写入型 CLI 命令**。

---

## 五、 后续阶段执行路线 (Next Stages)

本只读基线核查报告已完备证实了当前系统的客观事实与代码缺陷。无需停顿等待，立即自主进入后续阶段：
1. **阶段 B（历史治理纠正与更正报告）**：创建 `AUDIT/historical-correction/T000010-correction-report.md`，对 `T000010` 的代理审查事实与无效完成结论进行正式撤销声明（Additive Supersession）。
2. **阶段 C（实施 `T-CR-001`：修复 4 项协调缺陷）**：在 `src/uados/coordination.py` 中实施 C1、C2、C3、C4 的代码修复，输出缺陷分析与加固文档 `AUDIT/coordination-defect-analysis.md`。
3. **阶段 D（编写可复现回归单测与执行验证）**：在 `tests/test_coordination.py` 中增加针对 4 项缺陷的极限边界与对抗测试，运行完整验证。
4. **阶段 E（推进 `T-CR-002` 与性能调查）**：形成性能调查报告与流式验证机制。
5. **阶段 F（项目记忆与最终交付）**：更新状态与交付物。
