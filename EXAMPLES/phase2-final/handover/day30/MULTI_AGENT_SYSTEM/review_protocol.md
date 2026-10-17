# Independent adversarial review

Lifecycle authority: `MASTER_AGENT_WORKFLOW.md`. This document explains review substance for both recorded protocols. Protocol-2 major tasks additionally use the staged `debate_protocol.md` and `consensus_protocol.md`; legacy task approvals keep their recorded interpretation. Recorded consensus generates current independent plan/result approval records from eligible reviewer votes; a manually written report does not substitute for them.

The review question is: what plausible failure, missing assumption or better alternative could change the decision? The reviewer must inspect evidence rather than merely restating the implementer's explanation.

## Plan review

Before a major task is claimed, the implementer provides a plan covering problem, acceptance criteria, alternatives, scope, dependencies, validation, risks and recovery. The reviewer starts and acknowledges an independent session, reads relevant context and tests the plan's assumptions.

Examine at least the consequential risks: incomplete requirements, hidden shared state, compatibility, failure recovery, security/data boundaries, resource cost or experimental validity. Identify a falsifiable challenge, such as a migration that could lose records or a dataset split that could leak labels. Explain why the plan addresses the challenge or which change is required.

Record the review:

```sh
python -m uados --project . task review TASK_ID --session REVIEW_SESSION_ID \
  --stage plan --verdict approve \
  --challenge "Specific assumption tested and resulting judgment" \
  --evidence evidence/plan-review.md
```

Use `request_changes` when the plan lacks evidence or needs revision. Approval authorizes the planned tracked lifecycle; it does not grant external deployment, spending or data-sharing permission.

## Result review

After implementation and evidence recording, inspect the actual task, scoped files and result evidence. Compare the result with the approved plan and acceptance criteria. Reproduce a meaningful check when feasible, or explain why the review relies on supplied evidence. Do not mark an unavailable check as passing.

Record the same fields with `--stage result`. A major task's completion requires a current approved result by a distinct agent identity. The result review binds the reviewed task, scoped content and evidence fingerprint. Later edits to those inputs require a new result review; an older approval is not a blank authorization.

## Review record quality

Use `TEMPLATES/review.md`. Include inspected paths/revision, the strongest plausible challenge, findings with severity and evidence, verdict and unresolved limitations. An empty statement such as “looks good” does not preserve reasoning.

A second label cannot establish actual independence. The human team chooses a separate contributor or review process and verifies that the reviewer did not author the result. The CLI can check label inequality and recorded lifecycle conditions; it cannot prove who controlled a process.

## Disagreement and resolution

Keep objections and evidence visible. The implementer may revise the proposal, provide new evidence or record a trade-off for the human owner. Do not erase a rejected review to manufacture consensus. If a dispute blocks completion, record the task blocker and the specific decision or experiment needed to resolve it.

## Contributor history and independent review

Claiming a task preserves the contributor identity across handovers. A task author or any current or previous implementation contributor cannot supply its independent plan or result approval. Changing sessions or handing implementation to another agent does not erase that conflict of interest. Reviewer labels still require trusted human attribution.
