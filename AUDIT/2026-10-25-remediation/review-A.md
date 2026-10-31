# 评审者 A（架构与测试视角）— T000011 独立对抗式评审

## Solution
T000011 的已实现方案总体成立，建议接受。digest-only 事件 + 条件快照的架构决策自洽：快照触发条件（harvest_fingerprint 变化或序列号 %100）与审计/导出的实际消费范围精确对齐——我核对 protocol.py `all_evidence`（COLLECTIONS+tasks/decisions/experiments）与 compact 的 `evidence_names` 完全一致，保证"历史证据 harvest 等价于全量状态"的声明在结构上成立。2978a9d 修复到位：`_exclusive_copy` 用 "xb" 独占创建、微秒戳；compact 先做 `projection_drift`（含 journal_drift）拒绝再动备份，封掉漂移洗白。我亲自复跑全套测试：147 passed（35.9s）。

## Assumptions
- 单机信任模型不变：SQLite `synchronous=FULL` + flock 项目锁 + 原子替换/目录 fsync（storage.py connect/atomic_write/_exclusive_copy，亲验）；本评审不覆盖多机或对抗性磁盘层。
- 所有写入方均输出 canonical(sort_keys=True) JSON——loader 的裸字符串切片正确性依赖该不变量（commit_event/compact/rebuild_ledger 均经 `canonical()`，亲验）。
- 复现条件：`PYTHONPATH=src uv run --with pytest` 147 绿；生产账本已 compact（status 显示 event_count=849）；T000011 状态 pending、reviews 为空，本次评审即 major 门槛环节。

## Risks
- **快路径解析与 schema 演进的隐性耦合（storage.py:174-189）**。`raw.find(',"state":')` 取第一个匹配，而顶层键排序在 "state" 之前的 `sessions`、`mode_detection`、`counters`、`decisions`、`experiments`、`handovers` 全是容器；任一字段将来内嵌名为 "state" 的子键即会错位切片。后果是解析失败（fail-closed，可用性损失）或误读，代码无 canonical 性断言、无防护测试。"hash"/"summary" 因排序位置目前安全，但同样未文档化。
- **稳态写入放大未被定性**。每次 mutate 计算 `harvest_fingerprint` 两次（project.py:433,444，遍历全部证据记录含嵌套 manifest）+ `state_digest_value`（O(state) canonical 化）。元数据事件只省了 I/O 不省 CPU；独立复审观测的 ~40x state RSS 放大属此路径，但 F7 的"一次性工具"定性未覆盖它。
- **测试盲区（均经我沙箱实验确认功能正确但零回归防护）**：(a) SNAPSHOT_INTERVAL=100 节奏分支 tests/ 无覆盖，我在沙箱验证事件 100 确实嵌入快照；(b) 无单测断言"含证据的账本 compact 后历史 harvest 保留"（test_compact_rewrites 只用 notes；生产验证 177→178 仅人工做过一次）；(c) digest-only 头下 state 行与 state_digest 不一致的负路径（"state disagrees"）只在全状态事件上测过；(d) `event_anchor` 对 digest-only 事件无直接单测（沙箱验证其 state_sha256 与 state_digest_value 一致）。
- compact 备份将 2×3GB 原始字节留在 `.uados/` 内且不受任何完整性检查覆盖，磁盘翻倍已披露但只靠磁盘自身可靠性。

## Alternatives
- **快照分离存储**：快照状态放 SQLite 独立表（sequence→state），事件行恒小，流式加载无需字符串手术，解析与序列化解耦。实现方为兼容 legacy events.jsonl 选中内嵌方案，代价即上述 Risk 1。
- **compact 保锚点设计**：新链创世事件 pin 旧链头（checkpoint-by-construction），可使 pre-compact 外部锚点保持前缀可验证，而非现状的"完全不可验证"（F6 的文档化是诚实但激进的取舍）。

## Challenge themes
### Against the implementer's analysis
- 实现者将 F7/F8 定性为"已披露限制即可接受"。F8 方向性论证（只会多快照不会少覆盖）依赖 sha256 无碰撞，尚可；但稳态 mutate 的 O(全部证据) 双重指纹（Risk 2）在两个 commit 中既未测量也未跟踪。请实现者给出数百证据记录、MB 级 state 下的 mutate 延迟数据，或承认其为待跟踪项。
- 请解释为何节奏分支与"compact 后历史 harvest"未进入 12 个回归测试——两者我已在沙箱验证行为正确，补测成本极低，而恰是 compact 迁移最核心的两个不变量。

### Against the other reviewer's analysis
- 安全视角评审可能主张"快照应逐事件嵌入、中间状态须可独立重放验证"，并以此要求改方案。我要对抗：系统声明的完整性边界本就是"本地一致性检查，链无外部认证"（audit 输出 `integrity_limit` 字段原文），digest-only 未削弱任何既有保证——state 行始终被链尾 state_digest 锚定，逐事件哈希链覆盖中间事件；提高嵌入率只增体积不增防篡改强度。若以此为由 request_changes，是把边界外要求当缺陷。

## Verdict
**approve**（附跟踪项）。架构决策自洽、修复有 diff 证据、147 测试我亲自复跑通过；两个功能盲区经沙箱实验确认属补测问题而非设计缺陷。条件：(1) 补节奏分支与 compact 后 harvest 保留的回归测试；(2) 为 Risk 1 的序列化不变量加注释或断言，防止 schema 演进静默破坏 loader；(3) 将 mutate 稳态成本登记为已知限制。
