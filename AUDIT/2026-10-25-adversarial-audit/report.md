# UADOS 独立对抗式审计报告（2026-10-25）

**审计身份**：ZCode 独立审计（核心引擎子agent + 主会话交叉复核）
**方式**：多路对抗式审计（假设声明为假、逐条证伪）；仓库严格只读；实验均在 /tmp 隔离项目；生产账本仅运行只读 `audit`（实测 73.9s / 峰值 RSS 3.83GB，ok=true，event_count=829，projection_drift=[]，history_ok=false）。
**基线**：135 个测试 + 7 子测试全绿（uv/pytest）；`verify_scaffold.py`、`run_phase2_scenarios.py` 通过。

## P0 发现

### P0-1 账本 O(N×S) 病态膨胀（已证实）
- `storage.py:237-240` 每个事件内嵌完整结果状态；`project.py:61,68-81` 每次变更全量重渲染并重写 events.jsonl。
- 实测：829 事件共 2.97GB；单行尺寸 seq1=1.1KB → seq100=704KB → seq400=3.26MB → seq829=7.96MB。仅存头部约需 250KB。

### P0-2 ADR000003“流式引擎已部署”证伪
- `streaming_load_ledger` 唯一非测试调用者是只读 `coordination benchmark`（coordination.py:256）；status/audit/export/一切 mutation、trust checkpoint 均走 `load_ledger(keep_events=True)` 全量路径（project.py:202,221,531,620；trust.py:168,241）。
- 实测：生产账本 audit 73.9s / 3.83GB RSS；mutation 路径含 3GB 投影全量重写（历史上 20 分钟后 9GB 堆 SIGTERM 的路径未变）。ADR 引用的 53.84MB 为 tracemalloc 口径，与 RSS 不可比。

## P1 发现

### P1-3 Understanding Report 无限内嵌进 state["sessions"] 且永不裁剪
- `context.py:148-179` 报告内嵌 architecture/决策/交接/研究集合全文；`project.py:254,267-270` 每次刷新追加 {path,hash,content}，无清理。
- 实测：14 会话累计 252 份报告、7.54MB；S000011/S000012 两个 Phase 3 评审会话自 2026-10-13 起 active 未关闭（各 45/37 份），任何协作者变更都触发 refresh→追加→事件更大 的恶性循环（指纹跑步机）。

### P1-4 Phase 4 与全部 v2.0 文档提交绕过治理账本
- 账本计数 T:10、最后实现事件 826（2026-10-17T04:03Z）。git 提交 f75e1d5/c2f1f84/84dacc2 及 4 个 README 提交（10-17 12:56 CST 之后）均无任何 task/plan/review/debate/CR 记录，违反 MASTER_AGENT_WORKFLOW 的强制生命周期。

### P1-5 Phase 4“真实世界基准”为硬编码常量，报告叙事失实
- `tests/test_phase4_benchmarks.py:329-340` 实验脚本仅 dump 硬编码结果（B2_Exp_Run 0.28s）；mAP50 76.2→80.8、p=0.0032 等全部为字面常量；“企业级核心组件”为 4 行函数（AUDIT/benchmarks/benchmark1-software-relay/resilient_mod.py）。
- `AUDIT/phase4-benchmark-report.md` 将其表述为“确定性消融实验、采集严格数据、Production Gold Release”。

## P2 发现

1. 报告表格 B2_Exp_Run=0.2339s 与提交的 phase4-benchmark-metrics.json（0.2836s）矛盾；“50 项操作”实为 52 条。
2. `test_phase4_benchmarks.py:414-419,529` 每次运行覆写仓库 AUDIT/benchmarks/* 已提交证据（本审计的基线测试运行即覆写了 3 个文件，已 git checkout 还原），违反“证据一经引用不得覆盖”规则。
3. 中文 README“完整速查手册”缺 9/23 个顶层命令（trust/dispatch/coordination/review-bundle/improvement/adapter/export/context/upgrade）；README_EN 标题仍为 "UADOS v1.0"；.venv 内为过期非可编辑 uados 1.1.0；dist/ 无 2.0.0 wheel；FAQ“audit --repair 毫秒级瞬间重构”在自家 3GB 账本不成立（实测 74s）。
4. `PROJECT_MEMORY/architecture.md` 组件表缺 trust/coordination/dispatch/manifests/resilience 五个模块，新会话理解报告描述的仍是 Phase 2 架构。
5. 流式/全量加载语义不等价：`storage.py:157-176` 头提取分支的陈旧 last_state 可构造出两模式结论相反的账本。
6. `resilience.py:145-166` 捕获 BaseException 并把 KeyboardInterrupt/SystemExit 包装为 PermanentError；classify_error 子串匹配误报面大；typed RateLimitError 不解析 Retry-After；“确定性清单”的 bundle_id 含时间戳；review-bundle create 不产生任何账本事件。
7. `AUDIT/v2-production-review.md` 声称 "WAL/PRAGMA 强同步"，实际 storage.py 仅 `PRAGMA synchronous=FULL`（:95），从未启用 WAL。
8. 评审包 RB-1b770067cce282d5 由悬置 5 天的 S000011 于提交前 20 分钟为已完成的 T000010 生成，充当 Phase 4“评审闭环”证据；S000014（无关的 BEVFusion 评审）占据 SESSION_HANDOVER 顶部叙事。

## P3 发现

SYSTEM_IMPROVEMENT_LOG 5 项全部 proposed 未推进；3 个账本生成物滞留工作区未提交；“pyright 0 错误”无证据工件；读操作取排他锁并发度 1；evidence 可登记 .uados 内部路径造成永久审计失败；note 与 decision add 的 CLI 风格不一致。

## 经对抗验证成立的能力

哈希链逐链验证、单字节篡改全检出、序列空洞/状态失配 fail-closed、投影漂移先拒后修、原子写、safe_path 拒绝穿越与符号链接、Python 3.9 兼容（3.9.6 compileall 通过）、ADR000002 coordination 硬化逐项落实（含 `as_uri()+'?mode=ro'` 且 `uri=True` 生效）、review-bundle verify 单字节防篡改有效、markdown 链接全通、git 卫生良好、审计对 history_ok=false 的诚实披露。

## 修复指令（项目所有者 2026-10-25 批准）

1. 事件去全量化（P0-1）；2. 流式加载接入全路径并修正 ADR/v2 评审表述（P0-2）；3. 会话报告裁剪与 S000011/S000012 清理（P1-3）；4. 补记 Phase 4 治理、修正基准报告措辞（P1-4/5）；5. 测试产物改 /tmp、README 补 9 命令、architecture.md 补模块、修 BaseException。
