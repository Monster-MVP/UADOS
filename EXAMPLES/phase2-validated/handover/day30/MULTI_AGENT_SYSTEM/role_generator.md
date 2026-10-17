# Dynamic role generation

Lifecycle authority: [MASTER_AGENT_WORKFLOW.md](../MASTER_AGENT_WORKFLOW.md). Role generation turns task text, project mode and explicit task-type override into a review/implementation coverage plan. Task risk determines lifecycle depth under the master workflow. It is deterministic local planning, not autonomous model creation.

Generation uses the task's title/description, project mode and optional explicit type. Inspect risk and scope separately to assess coverage. Generate roles with concrete responsibilities and declared capability requirements. Inspect the generated plan for domain omissions; a title keyword is evidence of a likely need, not proof that the selected team is sufficient.

| Task family | Example coverage |
| --- | --- |
| Software database/performance | Architecture, implementation/backend, performance, security and testing |
| Research biosensor/materials | Principal investigation, literature, materials/domain expertise, experimental design, novelty and publication |
| Hybrid | Software correctness and research validity, with explicit responsibility for their interface |

The actual role list is in generated `role_plans.md`; examples do not prescribe a fixed team for every project. Choose registered contributors using [agent_selection.md](agent_selection.md). One contributor may transparently cover several roles when capabilities fit. Role count never substitutes for the independent reviewer quorum required by the master workflow.

If the task or coverage changes, regenerate/reassign before the next debate. A debate uses a fixed participant and assignment snapshot; do not change membership mid-round to remove an inconvenient challenge. Specialized domain capabilities are declarations requiring team verification.
