# UADOS v2.0 改进路线与生产演进建议 (Recommendations & Strategic Roadmap)

**文档编号**：UADOS-REC-20261017-FINAL  
**编制日期**：2026-10-17  
**基准版本**：UADOS v2.0 (Phase 3.3 Milestone)  
**面向对象**：核心架构团队、企业工程效能组与科研实验室维护人员  

---

## 一、 短期工程落地与加固建议 (Short-Term Engineering Recommendations)

### 1. 外部独立审查自动化与限流弹性处理 (Resilient Reviewer Orchestration)
- **现状分析**：在 Phase 3.1 与 Phase 3.3 中，向云端分发独立审查子 Agent 屡次遭遇上游模型 API HTTP 429 速率限制（Quota/Rate-Limit Exhausted）。由于系统恪守“严禁代理审查”红线，主 Agent 在 API 受阻时主动停止并报告，避免了伪造通过。
- **推荐改造**：
  1. **指数退避与抖动重试 (Exponential Backoff with Jitter)**：在子 Agent 调度层封装自适应限流重试器，对 HTTP 429 与 HTTP 503 实施动态等待退避；
  2. **多 Provider/多模型故障转移 (Multi-Provider Fallback Routing)**：支持在配置文件中指定 Reviewer 备选提供商池（例如：Anthropic API 耗尽时自动降级尝试 OpenAI Codex/GPT-4o 或本地部署的开源模型如 Llama-3-70B/Qwen-2.5-Coder）；
  3. **异步脱机审查工单 (Offline Review Ticket System)**：当所有可用外部模型均不可达时，系统自动生成防篡改的 Review Packet 并记录未完成工单，待配额充裕或网络畅通后执行离线批量批复。

### 2. 分布式协调后端标准插件实现 (Distributed Lease Plugin for Redis/Etcd)
- **现状分析**：加固后的 `MemoryLeaseBackend` 实现了严格的进程内租约隔离与原子 TTL 校验，但单机锁无法跨越多台物理机或容器节点。
- **推荐改造**：
  1. 基于现有 `LeaseBackend` 抽象基类，实现 `RedisLeaseBackend`（利用 Redlock 算法或 Lua 脚本原子执行 `SET resource token NX PX ttl`）与 `EtcdLeaseBackend`；
  2. 在 `pyproject.toml` 中将分布式后端作为可选扩展依赖（`pip install "uados[distributed]"`），保持核心库的零外部依赖特性。

### 3. CI/CD 工作流全量流式校验整合
- **现状分析**：`.github/workflows/ci.yml` 当前主要运行单测套件和基础场景。
- **推荐改造**：
  1. 在 CI 矩阵中增加专门的流式重放与内存基准步骤，在每次 PR 合并时验证 `streaming_load_ledger` 的内存不超过 100MB、耗时不超过 15s；
  2. 启用自动化 `pyright` 与 `ruff` 代码质量门禁，强制要求类型检查 0 错误后方可合并。

---

## 二、 中长期学术研究与复杂系统演进 (Medium-to-Long Term Roadmap)

### 1. 科研文献与全文本自动化连接器 (Automated Literature Mining & Zotero Sync)
- **目标**：打通与 Zotero、arXiv API、Semantic Scholar 的直接双向同步。
- **实施路径**：
  - 扩展 `research.py:add_source`，支持传入 DOI 或 arXiv ID 自动拉取 BibTeX、标题、摘要及 PDF 全文，并计算源文件 SHA-256 哈希值写入不可篡改证据库；
  - 结合 `paper-miner` Agent，在 `RESEARCH_MANAGEMENT/` 目录下自动构建领域技术树与差异化创新分析矩阵。

### 2. 外部密码学锚定与公钥可验证检查点 (Cryptographic Anchor & Notarization)
- **目标**：防范项目本地账本被单点物理篡改。
- **实施路径**：
  - 增强 `uados trust` 模块，支持将里程碑 Event Head Hash（如每 100 个事件或重大 Release）通过 OpenSSH/GPG 签名后，锚定至公共透明度日志（如 Sigstore / Rekor）或 Git Commit 标签中，建立端到端的第三方可验证信任链。

### 3. 跨租户与跨项目多智能体微内核协作架构
- **目标**：支持多个研发小组在独立工作区内并行开发，并在边界处进行安全上下文交换。
- **实施路径**：
  - 标准化 `Project.export` 与 `Project.import_context` 格式，支持通过精简的零知识摘要（Zero-Knowledge Summary）交换技术规范，确保在多团队协作时敏感代码不外泄、治理证据链完全闭环。

---

## 三、 生产环境运维最佳实践指南 (Production Best Practices)

1. **大文件与数据分离治理**：
   - 绝不可将 GB 级别的 SQLite 文件和高频事件日志 commit 进 Git 树，严格使用 `.gitignore` 排除 `/.uados/`。
   - 依赖项与大型数据集一律通过 DVC 或远程对象存储管理，仅在 UADOS 账本中记录文件的 SHA-256 指纹与版本元数据。
2. **规范提交与交接执行**：
   - 每次 Agent 会话结束前，必须显式调用 `session close`，生成清晰的 `SESSION_HANDOVER.md`，记录明确的后续步骤与已知的失败尝试。
   - 禁止绕过 CLI 直接手写修改生成的投影文件，所有事实变更必须以原子事件的形式在账本中沉淀。
