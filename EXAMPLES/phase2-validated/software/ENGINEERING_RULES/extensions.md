# Rule extension and continuous improvement

Extensions are maintained project policies, not arbitrary executable plugins. They let a project specialize the common workflow without hiding expectations in a conversation.

## Propose a bounded change

Use `TEMPLATES/extension.md` to identify the observed problem, evidence, proposed rule, affected roles, cost, enforcement mechanism and success measure. Link the failure or lesson that motivated it. State whether the rule is a contributor obligation, a CI check, or requires a future CLI implementation; prose alone does not create an automated gate.

Record a decision with alternatives, including retaining the present policy. Changes to lifecycle gates, risk classification, research validity or authority boundaries should be major tasks with independent plan and result review.

## Install the policy

Put approved rules in the appropriate maintained document and add a clear link from its directory README. Include owner, applicability, version or decision reference and revisit condition. Prefer a focused rule over a second conflicting workflow. Include a migration action for existing tasks when necessary.

Maintained policies are context inputs. Their modification invalidates an older session's context where applicable. After the change, refresh affected sessions, read the new Understanding Report and acknowledge its new hash before further tracked work. A contributor must not keep using an older acknowledgement to bypass a newly approved rule.

## Evaluate and revise

Assess whether the rule prevented the original problem and whether it added unreasonable effort or false alarms. Record evidence and exceptions. To retire or revise it, record the reason and review the change at the appropriate risk level. Preserve the historical decision and lessons; do not erase why the team adopted the rule.

Examples of useful extensions include a data leakage check for a particular experiment family, an API compatibility check, an approved instrument calibration protocol or a required migration dry run. External CI and integrations remain explicit team-owned configuration.
