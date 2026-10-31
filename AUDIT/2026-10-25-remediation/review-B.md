# 评审者 B（安全与信任边界）对 T000011 已实现工作的独立评审

依据：亲自审阅 f3730b5/2978a9d、storage.py/project.py/cli.py/trust.py、AUDIT/2026-10-25-remediation 两份记录；并在 /tmp 沙箱以 PYTHONPATH=src 自建项目做了 21 项实验（下文 A/B/C/D/E/F 编号），仓库只读。

## Solution
从安全视角接受该实现：digest-only 未削弱本地防篡改——每个事件的 state_digest 位于被哈希载荷内（storage.py:281-295），链验证逐行覆盖全部事件（storage.py:174-258）；实测篡改中间 digest-only 事件（C1）与仅改 state 行（C2）均被拒绝，harvest 快照覆盖等价（A4，A→B→A 均被捕获）。认证性由外部 SSHSIG 锚点承担且在 digest-only 头上可用（A5）。2978a9d 的 F1（O_EXCL+微秒备份，B6/D 实测）与 F4（compact 拒绝漂移）修复有效。残余风险集中在备份完整性与 F2 的恢复路径，属加固项，不阻塞。

## Assumptions
- （实测验证）信任模型：能写 .uados/ 的本地攻击者不被哈希链阻止，认证性完全依赖项目外 SSHSIG pin/私钥。全链重写+重写投影后 streaming_load_ledger 通过、audit ok=true（F 实验），与 audit 的 integrity_limit 声明（project.py:820）一致——边界被如实文档化。
- （代码+实验验证）canonical JSON 与字符串转义保证 `,"state":`/`,"summary":`/`,"hash":"` 只出现在顶层键位，这是流式加载快速切片与 event_anchor 的正确性前提（storage.py:174-208, 336-355）；切片错误只会导致解析异常或链失配，无静默通过路径。
- rebuild 场景中 .uados/state.json 是不可信输入：用末事件 state_digest 校验后才采用（project.py:193-202），导出面扩大不等于信任面扩大。

## Risks
- R1 备份是旧锚点唯一可验证载体却不受保护：compact 后旧检查点对活账本完全不能验证（trust.py:240-247；实测 B4 "Checkpoint project or sequence is missing"），归因只能靠 O_EXCL 备份（project.py:137-148, 338-345）；但备份 sha256 未写入 ledger.compact 事件（state["compaction"] 313-316 仅记 previous_head/bytes），audit 不检查备份存在性/完整性，_exclusive_copy 中途失败还会留下与完好备份不可区分的残缺文件。"可检测不可归因"因此弱于披露：删除备份即抹去归因材料且无痕迹。
- R2 cli.main 全局 KeyError/TypeError→"Invalid record structure"（cli.py:417-421）与 UadosError 同为 exit 2：真实实现 bug 被伪装成"用户数据非法"，诱导改数据而非报缺陷；实测 E2/E3 中 malformed 会话记录使 audit --repair 与 compact 同死，无工具化自愈——F2 只消除 traceback，未提供恢复路径。它不是篡改检测漏洞（伪造需先重算全链，见 E 实验），但多代理治理下错误分类失真会污染诊断与问责。
- R3 compact 无会话门禁（cli.py:273-274，classmethod 无 _session/acknowledge）：一条命令即可令全部历史锚点失效（B4），权限与写一条普通记录相同；单操作者可接受，protocol-2 多代理语境宜收紧。

## Alternatives
- 更保守的压缩：compact 前置要求存在 verify_checkpoint(require_current=True) 通过的锚点，并把 pre/post 头哈希与两个备份 sha256 记入 ledger.compact 事件；verify_checkpoint 增加"按 previous_head 归因历史检查点"模式（previous_head 已在链内，B5 证实单向链接存在），把"不可归因"升级为"归因到压缩事件"。
- F2 外科手术替代：把 sessions 嵌套记录（reports 的 path/hash）结构校验放进 streaming_load_ledger 的 schema 段（storage.py:162-164 目前只查顶层类型，该层已将 KeyError/TypeError 归一为 "Unreadable ledger"）；main() 兜底 catch 改用独立 error kind/exit code。

## Challenge themes
### Against the implementer's analysis
- F2 修复是症状级：请回应为何不在账本 schema 校验层修嵌套记录（语义正确且已有异常归一），而选 main() 全局兜底；并回应 R1——F6 披露诚实，但备份不受保护使其价值打折，是否接受"备份 sha256 入链"最小修复。
- compact 嵌入剪枝后最终状态（closed session 报告内容丢弃，project.py:298-316）：我核对 all_evidence 只读 COLLECTIONS+tasks/decisions/experiments，与 evidence_names 一致，等价性成立（A4）；请实现者确认该不变式写入测试。
### Against the other reviewer's analysis
- 若以"digest-only 使账本不自包含/切片路径脆弱"为由要求回退全量内嵌或全量 JSON 解析：切片安全性由两个可证不变式保证（Assumption 2），3GB 内存上界正是 f3730b5 的目标；测试火力应转向锚点×压缩交互（B4/B5）与备份完整性（R1），而非事件字节金样（compact 文档化重哈希使其天然脆弱，2978a9d 移除硬编码哈希是正确方向）。
- 若以"rebuild 依赖 state.json 扩大信任面"为由反对：state.json 是被 state_digest 校验的不可信输入（Assumption 3）；真正缺口是 digest-only 尾部在日志与 state.json 同时损坏时无演练测试，请补该负例。

## Verdict
approve。核心保证经独立实测成立：篡改检测（C1/C2）、harvest 覆盖等价（A4）、F1/F4 修复（B6/D1）、锚点可用性（A5）；残余 R1-R3 为加固级且 F6/F7/F8 披露诚实。建议将"备份 sha256 入链 + 锚点归因模式"与"F2 恢复路径/错误分类"记为 protocol-2 跟进任务，不阻塞 T000011 关闭。
