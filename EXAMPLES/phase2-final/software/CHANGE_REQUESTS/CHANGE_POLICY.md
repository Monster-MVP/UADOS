# Enterprise change policy

Lifecycle authority: [MASTER_AGENT_WORKFLOW.md](../MASTER_AGENT_WORKFLOW.md). For protocol-2 major modifications, use a structured change request linked to the task before its plan review. This gives the design-document/RFC/ADR process a durable record without replacing task ownership or acceptance gates.

Required fields are **Problem, Background, Alternatives, Decision, Impact, Risk and Validation**. Alternatives need at least two entries; evidence must be readable and relevant. Use [CR_TEMPLATE.md](CR_TEMPLATE.md) to prepare the content. Include compatibility, persistent-format impact, resource/authority constraints and recovery when relevant.

The recorded decision is proposed work until the task's governed review and completion establish its disposition. Generate roles, obtain independent analysis and adversarial challenges, and record consensus/plan approval before claim. After implementation, validate and conduct result debate/review over current contents. A material change to scope, assumptions, request or evidence requires renewed planning/review.

`CHANGE_REQUESTS/CR*.md` is generated from the ledger; the maintained template is the exception. Preserve rejected alternatives and superseded records. Use `decision add` for related architectural rationale when its separate fields aid long-term recovery; refer to the same evidence rather than duplicating mutable status.

Legacy protocol-1 tasks keep their recorded lifecycle. Enabling protocol 2 is explicit and preserves old events/tasks; do not retroactively invent change requests for historical approvals. Normal audit can propose improvements but never authorizes an automatic implementation or external deployment.
