# ADR: <decision title>

- Decision ID / date / owner:
- Related task / review:
- Status: proposed, accepted, superseded or rejected:

## Problem

What constraint or observed failure requires a decision? Include the workload, system boundary or hypothesis it affects.

## Alternatives

| Alternative | Benefits | Cost / limitations | Evidence |
| --- | --- | --- | --- |
| Retain the current approach | | | |
| | | | |

## Decision

State the selected approach precisely enough for another contributor to implement and review it.

## Reason

Explain how evidence and project constraints support the choice. Distinguish observations from assumptions.

## Evidence

Link measurements, prototypes, sources, experiments and review artifacts. Explain coverage limits.

## Risk and consequences

Record known disadvantages, compatibility/migration implications, failure recovery and the observation that would trigger reconsideration.

Use `decision add` to store the problem, at least two repeated `--alternatives`, decision, reason, repeated evidence paths and risk in the ledger. Link a significant decision with `--task TASK_ID` to an owned major task: it remains proposed until that independently reviewed task completes. Preserve a superseding decision rather than silently deleting the original rationale.
