# Major change request worksheet

Use this maintained worksheet to prepare the structured change-request operation. Generated `CR*.md` records come from the ledger; do not copy this worksheet into a manually approved record. See [CHANGE_POLICY.md](CHANGE_POLICY.md).

## Problem

Concrete trigger, observed behavior and affected users or research claims:

## Background

Current architecture, prior decisions, dependencies and relevant evidence:

## Alternatives

Describe at least two viable choices, including keeping the current behavior when meaningful. Compare costs, compatibility, validity and recovery:

## Decision

Proposed selected choice and why the available evidence favors it:

## Impact

Affected interfaces, persistent records, contributors, resources and migration/rollback:

## Risk

Failure modes, unsupported assumptions, authority/access constraints and accepted uncertainty:

## Validation

Falsifiable acceptance checks, exact procedures/commands, inputs/environment, expected outcomes and required evidence:

Link the task and readable evidence. Do not include credentials or confidential raw material.


## JSON submission shape

Replace every placeholder and create the referenced evidence before submission. Use `change propose TASK_ID --record evidence/change.json --session SESSION_ID`; the JSON file is maintained input, while the resulting `CR000001.md`-style record is generated.

```json
{
  "problem": "Observed trigger and impact",
  "background": "Current architecture and prior evidence",
  "alternatives": ["Preserve current behavior with stated cost", "Proposed bounded change with stated trade-off"],
  "decision": "Selected approach and rationale",
  "impact": "Affected interfaces, resources and migration",
  "risk": "Failure modes, uncertainties and recovery",
  "validation": "Falsifiable checks and expected outcomes",
  "evidence": ["evidence/change-design.md"]
}
```
