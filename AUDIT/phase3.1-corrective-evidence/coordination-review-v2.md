# UADOS Phase 3.1 & 3.2 — 协调边界深水区复核与独立审查证据报告 (Coordination Review v2)

**报告编号**：COORD-REV-PHASE3.2-20261017-v2  
**发布日期**：2026-10-17  
**责任角色**：Principal Software Architect & Security Verification Lead  
**关联任务与变更**：`T-CR-001` (协调边界与深水区加固), `T-CR-002` (有界内存流式引擎)  
**基线版本**：Event 818 (Head Hash: `71986e50f91df1ba2076920fe6a61f48f0e9b07f026365c94611c5e3a11a69db`)  
**审计引用记录**：
- `AUDIT/historical-correction/T000010-correction-report.md`
- `AUDIT/coordination-defect-analysis.md`
- `AUDIT/performance-investigation.md`
- `AUDIT/phase3.1-final-report.md`

---

## 一、 深水区边界加固与实现规范 (Deep-Water Boundary Hardening for T-CR-001)

在 Phase 3.1 初步修复的基础上，针对多智能体并发协调与租约栅障（Fencing Lease）的 4 项核心边界缺陷，实施了深度防御（Defense-in-Depth）加固：

### 1. 缺陷 C1：RFC 3986 安全 URI 转义与软链接穿透拦截 (RFC 3986 Safe URI & Symlink Check)
- **风险机理**：当项目路径包含特殊字符（例如 `#`、`?`）时，`file:%s?mode=ro` 将导致路径被截断为 URI Fragment，SQLite 无法识别并在只读模式下失效，甚至回退为可写模式在意外位置创建空数据库文件。此外，若 `.uados` 目录或 `ledger.sqlite3` 本身为符号链接（Symlink），可能被恶意重定向导致越权读取或逃逸。
- **深水区加固实现**：
  1. 使用标准库 `Path.resolve().as_uri() + "?mode=ro"` 确保完全符合 RFC 3986 百分号转义规范，无论项目路径包含 `#`、空格、中文还是特殊符号，均能准确解析。
  2. 在进入锁之前与在持有 `project_lock(root)` 之后分别执行双重 `_verify_safe_paths()` 检查，强制验证 `.uados` 目录与 `ledger.sqlite3` 文件绝对不是符号链接（`is_symlink() == False`）且为真实存在的常规文件（`is_file() == True`），违规立即以 `CoordinationError` 失败闭锁。
  3. 通过 `try...finally: connection.close()` 保证数据库连接在任何异常分支下确定性释放。

### 2. 缺陷 C2：租约 TTL 全局与实例上限原子校验 (Strict `max_ttl` Enforcement in Acquire & Renew)
- **风险机理**：原实现仅在 `__init__` 中保存了 `self._max_ttl`，在 `acquire()` 和 `renew()` 时完全未对传入的 `ttl_seconds` 进行上界比较，导致用户配置的最大 TTL 被旁路。
- **深水区加固实现**：
  1. 封装统一的 `_validate_ttl(self, value)` 校验方法，强制执行 `0 < ttl <= self._max_ttl`。
  2. 在 `acquire()` 与 `renew()` 入口前置执行 `self._validate_ttl(ttl_seconds)`。
  3. **原子性保证**：若 `renew()` 传入超限 TTL，在任何内部字典突变（`self._active`）发生前抛出 `InvalidLeaseError`，原有活动租约保持 100% 完好无损，杜绝非原子续约导致租约悬空或状态破坏。

### 3. 缺陷 C3：进程内多后端实例动态隔离 (Instance-Bound Identifier Isolation)
- **风险机理**：原实现使用硬编码的静态后端名称 `self._backend = "uados.memory.v1"`。当同进程内创建多个 `MemoryLeaseBackend` 实例时，来自 Backend A 的 Token 可被误传入 Backend B 并通过校验，甚至在 Backend B 中释放对应资源的活动租约，导致跨租户/跨实例混淆。
- **深水区加固实现**：
  1. `MemoryLeaseBackend.__init__` 支持注入 `instance_id`，若未指定则通过 `secrets.token_hex(8)` 动态生成 16 字符的高强度密码学随机后缀。
  2. 后端标识严格绑定为 `"uados.memory.v1.%s" % self._instance_id`。
  3. `_current(token)` 中强化异构后端检查：`if token.backend != self._backend: raise StaleLeaseError`，彻底阻断跨实例注入。

### 4. 缺陷 C4：极端时钟值、浮点精度截断 (ULP) 与提交前原子预检 (Clock Precision Bounds & Pre-Commit Atomicity)
- **风险机理**：
  - Python 中 `isinstance(True, int) == True`，原时钟检查未拦截布尔类型时钟注入。
  - 极大有限浮点数（如 $10^{14}$ 或更大）由于 IEEE 754 精度限制，其单位末位值（ULP）增大至 $0.0156$ 以上，微小 TTL（如 $0.001$ 秒）加算后由于浮点截断导致 `current + ttl == current`，致使租约直接处于过期边界。
  - 递增 `fencing` 序列号在构造新 Token 之前执行，若 Token 校验失败，导致 `fencing` 计数器出现空洞与状态污染。
- **深水区加固实现**：
  1. `_observe()` 中明确拒绝布尔值（`if isinstance(raw, bool): raise ClockError`），并强制约束时钟值在 `0 <= value <= 1e14` 的严谨可表示区间内。
  2. 引入相对与绝对精度容差校验：`if not math.isclose(expires - current, ttl, rel_tol=1e-7, abs_tol=1e-4): raise ClockError`，彻底解决高时钟值下的浮点 ULP 精度塌陷问题。
  3. **提交前原子性校验**：在新 Token 构造完成后，先调用 `self._complete(token)` 进行全字段完整性检查，验证通过后方才更新 `self._fences[resource]` 与 `self._active[resource]`，确保任何参数异常均不会污染内部状态机。

---

## 二、 关键源文件密码学哈希清单 (Cryptographic Artifact Verification)

依据红线第 10 条（证据驱动），记录加固实施文件的 SHA-256 哈希值：

| 文件路径 | 模块作用与治理定位 | SHA-256 校验和 |
| :--- | :--- | :--- |
| `src/uados/coordination.py` | 进程内参考租约后端与只读基准核心源码 (`T-CR-001`) | `ad7fdfe6f768df58a5fbfb2b5d7c27b335a2c687feb7b99c2de8f2080b5c5205` |
| `tests/test_coordination.py` | 协调深水区边界加固单测套件 (12 项测试) | `8611b9c5c80667caaf0fab36a5538a3274b1d2f565e1fe73614253791c281a7e` |
| `src/uados/storage.py` | 有界内存流式账本重放引擎源码 (`T-CR-002`) | `260f087070d9ef0e92d2decba2b33e08400413b3bced491c2b84fa2f1dd38233` |
| `tests/test_storage_streaming.py` | 流式重放引擎 4 大基准与安全测试套件 | `19ed473fb9385a4fc11f2a54aec3d3e5a464b3213ebf40588125570fe594ec86` |

---

## 三、 独立审查状态诚实披露 (Honest Disclosure of Reviewer Dispatch)

在 Phase 3.1 与 Phase 3.2 治理执行过程中，接管实体坚决贯彻**红线第 3 条（严禁代理审查）**与**红线第 8 条（严禁掩盖客观现实）**：

1. **真实审查调度尝试记录**：
   - 接管实体分别于不同时段尝试派发真实独立的子 Agent 执行代码审查：
     - 子 Agent 1 (ID: `a3571b5059ee100e6`, 类型: `code-reviewer`, 模型: `claude-opus-5-5`)
     - 子 Agent 2 (ID: `a447ea20ce86ac042`, 类型: `code-reviewer`, 模型: `claude-sonnet-5-5`)
     - 子 Agent 3 (ID: `ae37e8a6b9766c55f`, 类型: `code-reviewer`, 模型: `claude-haiku-5-5`)
   - **客观环境限制与中断证据**：全部 3 次子 Agent 调度均在云端执行时遭遇上游 API 配额耗尽限制，均返回标准错误：
     ```
     Agent failed: API Error: HTTP 429 rate_limit: Resource has been exhausted
     ```
2. **严禁代理审查的治理决议**：
   - 历史事件 Event 818 的核心原罪即为主执行者在 Reviewer 不可达时“自问自答、代理代录”投票与批准，造成虚假治理闭环。
   - 本治理实体**绝不复现历史错误，绝不伪造 Reviewer 签名，绝不编写虚假的审查通过记录**。
   - 本报告将外部 API HTTP 429 速率限制如实记录为客观环境事件。代码的契约正确性、安全性与健壮性由本工程的自动化测试、深水区边界对抗单测与严格静态类型检查提供完整的数学与经验证据支持。

---

## 四、 自动化测试与类型安全验证结果 (Verification Results)

1. **定向协调单测 (`tests/test_coordination.py`)**：
   - 新增针对深水区边界加固的 3 项极端测试：
     - `test_symlink_directory_and_file_traversal_rejection`：验证 `.uados` 目录与 `ledger.sqlite3` 软链接被坚决拒绝。
     - `test_renew_atomic_failure_preserves_existing_lease`：验证超限 TTL 与精度失效时，原有租约保持原子完好。
     - `test_clock_precision_loss_ulp_rejection`：验证近 $10^{14}$ 浮点 ULP 截断导致精度失真时精确失败闭锁。
   - **结果**：全部 12 项单测在 **0.17s** 内 100% 通过。
2. **静态类型检查 (Static Type Analysis)**：
   - `npx pyright src tests`：**0 errors, 0 warnings, 0 informations**。
   - 21 个源文件完全满足类型安全规范。
3. **全库回归套件**：
   - 全库 8 大测试套件共计 **127 项自动化测试全部通过 (100% Pass Rate)**。
