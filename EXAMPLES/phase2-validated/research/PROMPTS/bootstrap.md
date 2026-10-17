# Bootstrap prompt

You are a new contributor to this UADOS project. Establish context before modifying implementation or running a substantive experiment.

Read `MASTER_AGENT_WORKFLOW.md`, `AGENTS.md`, `PROJECT_STATE.md`, `SESSION_HANDOVER.md`, `PROJECT_MEMORY/`, `DEVELOPMENT_LOG.md`, `DECISION_RECORD.md` and relevant engineering/research rules. Inspect underlying evidence for the area you will work on. Identify missing resources and assumptions without inventing facts.

Start a session with `python -m uados --project . session start --agent <stable contributor label>`. Read the printed Understanding Report and its listed source documents. Check objective, phase, architecture, completed work, problems, risks, resources and recommended next actions. Acknowledge the printed session ID and exact report hash only after that inspection.

Explain the next concrete task, its acceptance criteria, risk, scope and dependencies. Reuse an appropriate existing task or create one through the CLI. Obtain independent plan approval for major work before claim. If context changes, refresh and acknowledge the new report before further tracked work.

Preserve important reasoning in decisions and notes, attach meaningful evidence, and close the session with a handover. Keep implementation edits and maintained notes separate from generated projections. Treat the CLI's acknowledgements and agent labels as workflow records, not proof of comprehension or identity.
