# Agent client compatibility

UADOS provides a common project record and lifecycle through [MASTER_AGENT_WORKFLOW.md](../MASTER_AGENT_WORKFLOW.md). Its native entry files request explicit reading of that authority; this is a compatibility contract, not proof that a product obeyed it. No provider credentials, hidden API calls or commercial client launch are required by the local CLI.

Official loader documentation was checked on **2026-10-12**. Loader behavior can change; recheck product documentation when upgrading.

| Client | UADOS entry | Documented discovery and relevant limit |
| --- | --- | --- |
| Codex | Root `AGENTS.md` | Loads instructions from root toward working directory; `AGENTS.override.md` and configured fallbacks can take precedence. Combined project instructions default to a 32 KiB limit. Keep this adapter short and explicitly read the master. [Official documentation](https://developers.openai.com/codex/guides/agents-md) |
| Claude Code | Root `CLAUDE.md` importing `@MASTER_AGENT_WORKFLOW.md` | Markdown imports are supported. Native `AGENTS.md` discovery is version/settings dependent; the supplied CLAUDE entry avoids relying on it. If import is unavailable, read the master explicitly. [Official documentation](https://code.claude.com/docs/en/memory) |
| Cursor | `.cursor/rules/uados.mdc` | Project rules use `.mdc` with frontmatter; plain `.md` in this directory is ignored. `alwaysApply: true` activates the wrapper. Referenced files are not automatically inlined, so its body instructs an explicit read. Root `AGENTS.md` is also supported. [Official documentation](https://cursor.com/docs/rules) |
| Qoder | Root `AGENTS.md` | Automatically recognizes AGENTS. Native `.qoder/rules` take precedence on conflicts; active rule content has a combined size limit. The entry uses a plain file path and explicit read instruction, not an assumed import. [Official documentation](https://docs.qoder.com/user-guide/rules) |
| ZCode | Root `AGENTS.md` | Documents global and workspace AGENTS sources. CLAUDE migration is onboarding behavior, not continuous runtime loading. This contract does not assume nested discovery, imports or a shared merge algorithm. [Official documentation](https://zcode.z.ai/en/docs/agents) |

Adapters do not duplicate lifecycle rules. `.cursor/rules/uados.md` remains a portable human reference alongside the actual `.mdc` wrapper. Native product instructions may change precedence; inspect them without silently overwriting existing files during adoption.

Role selection produces provider-neutral assignments and a dispatch packet with task/context/instructions. A human or authorized host starts actual independent contributors and supplies their results through the CLI. Capability labels and agent labels are declared metadata, not verified model skills or identity. The team must establish actual independence.

Local validation covers maintained file parity, packaged hidden/nested assets, CLI behavior and simulated identity switching. It does not claim end-to-end execution of Codex, Claude Code, Cursor, Qoder and ZCode. Commercial-client integration, provider dispatch, native hooks, remote authentication and client-specific automated enforcement remain explicit integrations to test.
