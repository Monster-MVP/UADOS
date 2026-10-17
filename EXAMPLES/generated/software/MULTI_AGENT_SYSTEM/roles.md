# Roles and ownership

| Role | Responsibility | Durable output |
| --- | --- | --- |
| Coordinator | Translate the objective into owned tasks, dependencies and resource decisions | Task records, prioritization rationale and handover |
| Implementer | Understand context, claim work, make the change and validate it | Implementation, task evidence and technical notes |
| Architect | Examine boundaries, contracts and long-term consequences | ADR or RFC with alternatives and risks |
| Researcher | Frame hypotheses, design experiments and interpret results | Protocol, experiment records, analysis and negative findings |
| Reviewer | Challenge assumptions independently and inspect the plan or result | Review verdict, challenge and supporting evidence |
| Quality / security specialist | Investigate failures and domain-specific risks | Reproducers, findings and bounded mitigations |
| Human owner | Set priorities and authorize actions beyond contributor authority | Explicit project direction and recorded decisions |

Roles are responsibilities, not permissions automatically provisioned by UADOS. Agent labels identify records; authentication and authority remain team policy or external integrations.

## Ownership contract

An implementer owns an active task's recorded work and evidence. A reviewer owns the review judgment, not the implementation. The coordinator owns conflict resolution and dependency ordering. If an essential owner leaves, another contributor must inspect current context and explicitly take over through the available task lifecycle; do not impersonate the departed contributor.

Claims coordinate scoped paths and prevent conflicting tracked claims under the CLI's rules. Do not assume a file is protected from direct edits. Keep shared policy and central architecture changes out of parallel scopes unless contributors have agreed how to sequence them.

## Delegation packet

A useful delegation contains task ID, objective, acceptance criteria, risk, scope, dependencies, relevant decisions and evidence paths, resource constraints and the expected handover. Delegate a coherent responsibility. The receiving contributor should report assumptions and conflicts before doing dependent work.

Do not delegate a request for endorsement. Ask the reviewer to identify a concrete way the proposal might fail, inspect the relevant artifacts and give a reasoned verdict.
