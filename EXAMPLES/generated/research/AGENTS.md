# Contributor instructions

Follow `MASTER_AGENT_WORKFLOW.md` before editing project implementation or running a substantive experiment. Start a UADOS session with a stable agent label, inspect its Understanding Report and acknowledge the exact report hash. Track the work with that session. Refresh and acknowledge again if the CLI reports stale context.

Read `PROJECT_MEMORY/architecture.md`, the current task record, its dependencies, relevant decisions and the relevant engineering or research rules. State missing resources and unresolved assumptions explicitly. Inspect existing work before creating overlapping work.

Claim the task before implementing it. A task marked `major` needs an independent approved plan before claim and an independent approved result before completion. A review must challenge assumptions, inspect relevant files and evidence, and use a different agent label from the implementer. A distinct label alone is insufficient evidence of an independent human or model review: the team is responsible for real independence.

Edit maintained documents and implementation files. Never hand-edit generated `PROJECT_STATE.md`, `DEVELOPMENT_LOG.md`, `DECISION_RECORD.md`, `SESSION_HANDOVER.md`, `PROJECT_MEMORY/tasks.md`, `PROJECT_MEMORY/knowledge.md`, `PROJECT_MEMORY/session_reports/`, `RESEARCH_MANAGEMENT/experiments.md`, `.uados/state.json` or `.uados/events.jsonl`. Record durable notes with the CLI or under `PROJECT_MEMORY/notes/`. Use tracked decisions for significant choices.

Validate behavior with checks proportionate to risk. Record the command, result and an evidence file. Do not describe an unexecuted test as passing, a missing source as an empty result, or an experiment as reproducible without its inputs and environment. Preserve failures and negative findings.

Do not overwrite another contributor's active work. Stop and record a blocker when ownership conflicts, required data is unavailable, or a plan requires authority you do not have. A task's paths describe ownership and review scope, not an operating-system sandbox. Coordinate changes outside that scope before proceeding.

At a stopping point, close the session with a concise summary, actionable next steps, blockers and failed approaches. Leave enough evidence and rationale for a contributor with no access to your chat. Do not put credentials, confidential raw data or secrets into prompts, notes or evidence.
