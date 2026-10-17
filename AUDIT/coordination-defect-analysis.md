# UADOS 协调模块缺陷深度分析与加固报告 (Coordination Defect Analysis & Hardening)
## 针对 `src/uados/coordination.py` 4 项核心边界缺陷的根因分析与工程修复实现 (`T-CR-001`)

**报告编号**：DEFECT-ANALYSIS-20261017-v1  
**生效阶段**：Phase 3.1 (`T-CR-001`)  
**分析与实施角色**：Principal Software Architect & Security Verification Lead  
**受影响文件**：`src/uados/coordination.py`  
**测试覆盖套件**：`tests/test_coordination.py`  

---

## 一、 缺陷全景与背景

在前期任务 `T000010` 的审查治理纠正中，独立的 Phase 3 安全与验证审查员（`Phase3-Security-Reviewer` 与 `Phase3-Validation-Reviewer`）在 `src/uados/coordination.py` 中定位出 4 项未被现有 116 项回归测试覆盖的源代码安全边界缺陷。

为彻底消除由于代理审查导致的隐患，接管治理实体通过 `T-CR-001` 正式实施了精准的源码加固，并在本报告中做全量技术披露。

---

## 二、 4 项缺陷深度剖析与修复实现

### 1. Defect C1: SQLite URI 特殊字符转义与只读边界失效
- **缺陷位置**：`src/uados/coordination.py:211` (`benchmark_history` 函数)
- **原始易受攻击代码**：
  ```python
  uri = "file:%s?mode=ro" % ledger.as_posix()
  ```
- **根因分析 (Root Cause)**：
  SQLite URI 规范中，`#` 字符被解释为 URI 片段（Fragment）的起始标识符。若工程目录或临时测试路径中包含 `#`（例如 `p#frag/ledger.sqlite3`）或 `%`、`?` 等保留字符，`as_posix()` 未转义字符串会导致 URI 在 `#` 处被截断，丢失后半部分路径及 `?mode=ro` 查询参数。SQLite 默认将截断后的路径作为新的数据库文件打开并以读写创建模式运行，造成在截断路径处静默创建 0 字节文件（例如 `p`），破坏了“只读基准度量绝不修改文件系统”的安全性契约。此外，原实现未前置校验底层账本文件是否为真实存在的常规文件，在文件缺失时可能引发非预期的创建行为。
- **加固与修复实现**：
  1. 使用标准库 `Path.resolve().as_uri()` 实施全量 RFC 3986 百分号转义（例如 `#` 自动编码为 `%23`），确保完整路径与 `?mode=ro` 参数完整传递给 SQLite 驱动。
  2. 在获取锁前后双重前置校验 `ledger.is_symlink()` 与 `ledger.is_file()`，对软链接及非常规文件或不存在文件立即 Fail-Closed 抛出 `CoordinationError`。
  3. 采用显式的 `try...finally: connection.close()` 结构，确保连接即时确定性释放，避免依靠事务上下文管理器引发连接悬挂。
  ```python
  if ledger.is_symlink():
      raise CoordinationError("The ledger must not be a symlink.")
  if not ledger.is_file():
      raise CoordinationError("The ledger file does not exist or is not a regular file.")
  with project_lock(root):
      if ledger.is_symlink():
          raise CoordinationError("The ledger must not be a symlink.")
      if not ledger.is_file():
          raise CoordinationError("The ledger file does not exist or is not a regular file.")
      uri = ledger.resolve().as_uri() + "?mode=ro"
      connection = sqlite3.connect(uri, uri=True, timeout=30)
      try:
          state, events = load_ledger(connection)
      finally:
          connection.close()
  ```

---

### 2. Defect C2: 租约配置的 `max_ttl` 上限未强制执行
- **缺陷位置**：`src/uados/coordination.py:77, 144, 179` (`MemoryLeaseBackend`)
- **原始易受攻击代码**：
  ```python
  # __init__
  self._max_ttl = self._ttl(max_ttl) # 仅存储于实例变量
  # acquire / renew
  ttl = self._ttl(ttl_seconds) # 仅校验了全局 MAX_TTL (24h)，从未与 self._max_ttl 比较
  ```
- **根因分析 (Root Cause)**：
  虽然构造函数允许传入自定义的 `max_ttl` 并校验其格式，但在后续的 `acquire()` 和 `renew()` 操作中，仅通过静态方法 `_ttl()` 对全局默认常数 `MAX_TTL`（24小时）进行了上限比对，从未校验请求的 `ttl_seconds` 是否超过实例配置的 `self._max_ttl`。这导致调用者显式配置更小防御窗口（例如 `max_ttl=1.0`）时，系统静默允许申请 `60.0` 秒甚至更大的租约，使调用方对超长持有的安全防御失效。
- **加固与修复实现**：
  新增实例级 TTL 校验方法 `_validate_ttl(self, value)`，统一在 `acquire()` 与 `renew()` 入口处校验：
  ```python
  def _validate_ttl(self, value):
      ttl = self._ttl(value)
      if ttl > self._max_ttl:
          raise InvalidLeaseError("Lease TTL must not exceed configured backend maximum.")
      return ttl
  ```
  在修改任何栅栏编号（Fencing）或活跃租约字典（`_active`）之前，对越界 TTL 立即抛出 `InvalidLeaseError`，确保配置的防护上限严格生效。

---

### 3. Defect C3: 跨后端实例 Token 混淆与租约隔离击穿
- **缺陷位置**：`src/uados/coordination.py:82, 138` (`MemoryLeaseBackend`)
- **原始易受攻击代码**：
  ```python
  self._backend = "uados.memory.v1" # 静态常量
  # _new_token
  nonce = "%s:%d:%0.9f" % (self._backend, fencing, issued)
  ```
- **根因分析 (Root Cause)**：
  在同一进程内创建的所有 `MemoryLeaseBackend` 实例，均使用完全相同的字符串 `"uados.memory.v1"` 作为标识。由于 Nonce 仅由 backend 字符串、fencing 整数和 issued 浮点数格式化生成，若两个独立的后端实例具有相同的时钟与相同的资源/持有者，它们将签发完全一致的 `LeaseToken`。
  当后端 A 签发的 Token 被传入后端 B 的 `validate()` 或 `release()` 时，后端 B 的 `_current()` 检查 `token.backend != self._backend` 将错误判定为匹配，从而允许后端 B 验证通过甚至释放后端 B 自身持有的活跃租约，造成严重的进程内租约混淆与跨实例越权。
- **加固与修复实现**：
  1. 为 `MemoryLeaseBackend.__init__` 引入可选的 `instance_id` 入参，支持确定性测试注入；在未指定时，通过加密安全随机数 `secrets.token_hex(8)` 动态生成 16 位唯一的实例标识。
  2. 将后端实例标识绑定为 `"uados.memory.v1.%s" % self._instance_id`，保证不同实例签发的 Token 在物理隔离层拥有不同的 backend 签名。
  3. 当异构或不同实例的 Token 传入 `_current()` 时，`token.backend != self._backend` 准确捕获并抛出 `StaleLeaseError("Lease token belongs to another backend.")`。

---

### 4. Defect C4: 极端有限时钟值精度折叠与超长 Nonce 异常
- **缺陷位置**：`src/uados/coordination.py:114-122, 138` (`MemoryLeaseBackend`)
- **原始易受攻击代码**：
  ```python
  def _observe(self):
      value = float(self._clock())
      # 仅检查了 math.isfinite 与 value < self._last_now
      return value
  # acquire 中计算：
  token = self._new_token(resource, holder, fencing, current, current + ttl)
  self._active[resource] = token # 状态已变！
  # 后续 validate 时由于 nonce 格式化膨胀超长引发 InvalidLeaseError
  ```
- **根因分析 (Root Cause)**：
  1. **浮点精度折叠 (Precision Collapse)**：当注入的时钟值极大（例如 `1e308`，或接近 IEEE 754 双精度上限 `2^53`）时，`current + ttl` 的浮点数加法发生精度舍入折叠，满足 `current + ttl == current`。计算出的 `expires_at` 等于 `issued_at`，租约在签发瞬间即被认定过期，或产生无限持有的逻辑异常。
  2. **Nonce 字符串溢出**：`_new_token` 中使用 `"%0.9f" % issued` 进行定点浮点数格式化。若 `issued = 1e308`，格式化后产生超过 300 个字符的文本，远超系统文本字段上限 `MAX_TEXT=256`。
  3. **非原子性状态突变 (State Mutation Before Validation)**：在原 `acquire()` 与 `renew()` 实现中，在创建 Token 后未先行完整性验证，便提前递增了 `self._fences[resource]` 并存入了 `self._active[resource]`。后续调用 `validate()` 时抛出 `InvalidLeaseError`，但后端内部状态已处于损坏/污染状态。
- **加固与修复实现**：
  1. **严格时钟域约束与布尔防护**：在 `_observe()` 中禁止布尔类型（Python 中 `bool` 是 `int` 子类），限制时钟值非负且位于合理可表示精度范围 `0 <= value <= 1e14`（$10^{14}$ 秒约为 317 万年，满足真实单调时钟与历元时间需求且双精度下 1 微秒精度不失真）。
  2. **严格过期增长校验**：在 `acquire` 与 `renew` 中强制要求 `expires = current + ttl` 必须严格满足 `expires > current and math.isfinite(expires)`，否则抛出 `ClockError`。
  3. **提交前预检原子性保障**：在变更 `self._fences` 与 `self._active` 前，强制调用 `self._complete(token)`，验证 Nonce 长度、各字段合法性及有界性。只有预检 100% 通过后，才持久化内存状态。

---

## 三、 架构安全不变量与设计保障

经本次加固，`src/uados/coordination.py` 全面确立了以下 5 项运行时核心不变量：
1. **URI Safe-Query Invariant**：所有只读 SQLite 连接严格使用 RFC 3986 百分号转义，且确保连接仅指向存在的常规文件。
2. **Cap-Enforced Duration Invariant**：租约获取与续期的有效时间严格受控于实例配置的 `_max_ttl` 与全局 `MAX_TTL` 的交集。
3. **Backend-Instance Cryptographic Isolation**：同进程中不同协调后端实例严格隔离，互不识别、互不影响彼此持有的资源租约。
4. **Clock-Representation & Monotonic Strictness**：时钟数值必须是有界、正向递增、非布尔且精度不可折叠的实数。
5. **Pre-Commit Atomicity**：租约 Token 的生成与结构完整性校验严格在修改任何后端内部状态之前完成，任何构造失败均保持后端状态的原生纯洁性。
