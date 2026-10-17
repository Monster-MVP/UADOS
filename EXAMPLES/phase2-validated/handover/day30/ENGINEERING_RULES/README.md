# Engineering rules

These are maintained team policies. They turn a project's risks into reviewable work rather than replacing judgment with a universal checklist.

- `software.md`: architecture, interfaces, dependencies and operational behavior.
- `quality.md`: risk classification, evidence and completion criteria.
- `security.md`: trust boundaries, secrets, data and executable research commands.
- `extensions.md`: introducing or changing project-specific rules.

Read the rules relevant to the task before acknowledging context. Apply software rules in software and hybrid modes. Apply research rules in research and hybrid modes; research code still needs appropriate software quality and security review.

The CLI implements a finite set of gates: acknowledged context, task ownership/dependencies, evidence requirements and independent plan/result approvals. Protocol-2 tasks add evidence-backed plans; major work adds change requests, role coverage and staged debate/consensus. The single lifecycle authority is `MASTER_AGENT_WORKFLOW.md`; `MULTI_AGENT_SYSTEM/` and `CHANGE_REQUESTS/` explain the specialized records. It does not automatically enforce every policy statement or configure CI, identity providers, Git hosting, provider dispatch or deployment.

If rules conflict, follow applicable law and organizational constraints, then explicit project authorization, then the project's approved policies. Record a policy conflict and its resolution before consequential work. Exceptions need a named reason, bounded scope, owner and expiry or revisit condition; do not silently weaken a rule.
