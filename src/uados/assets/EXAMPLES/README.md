# Worked workflows

These walkthroughs use the actual CLI, with IDs/hashes copied from its JSON output. Replace uppercase placeholders. They describe a local trusted-team workflow; starting an independent reviewer is the responsibility of your agent environment or team.

## Routine software work and agent handover

Initialize a new directory after installing UADOS:

```sh
python -m uados init ./example-app --name "Example app" \
  --objective "Build and validate a small service" --mode software
python -m uados --project ./example-app session start --agent implementer-A
python -m uados --project ./example-app session acknowledge SESSION_A \
  --report-hash REPORT_HASH_A
python -m uados --project ./example-app task add --session SESSION_A \
  --title "Validate input boundaries" \
  --description "Reject malformed inputs and preserve valid input behavior; verify both" \
  --risk routine --scope src/validator.py
python -m uados --project ./example-app task claim TASK_ID --session SESSION_A
```

Create the implementation and run the relevant checks. Save actual results at `example-app/evidence/validation.txt`; do not use fabricated passing output. Then record and complete:

```sh
python -m uados --project ./example-app task record TASK_ID --session SESSION_A \
  --summary "Implemented input boundaries; valid and malformed cases checked" \
  --evidence evidence/validation.txt
python -m uados --project ./example-app task complete TASK_ID --session SESSION_A
python -m uados --project ./example-app session close SESSION_A \
  --summary "Boundary validation completed with recorded checks" \
  --next "Review the validator task evidence and define the next service behavior"
python -m uados --project ./example-app session start --agent implementer-B
```

Agent B reads the new report and source documents, acknowledges its hash and continues. Completed work, evidence and next action come from the project record rather than Agent A's chat. If maintained context was edited between commands, refresh and acknowledge before proceeding.

## Major change with independent review

Create a major task with explicit scope and a plan artifact. A genuinely separate reviewer starts and acknowledges a session, challenges the plan and records:

```sh
python -m uados --project . task review TASK_ID --session REVIEW_SESSION \
  --stage plan --verdict approve \
  --challenge "Examined migration failure paths; staged writes preserve existing records" \
  --evidence evidence/plan-review.md
```

The implementer refreshes and acknowledges because the review changed project context, then claims the task. After implementation, validation and `task record`, the reviewer refreshes and acknowledges, inspects the actual result and records a result review. The implementer refreshes and acknowledges again before completion.

The challenge text above is an example of form, not proof that a migration was tested. Each team's review must refer to its actual artifacts.

| Attempt | Expected behavior |
| --- | --- |
| Claim a major task without a current independent plan approval | Rejected |
| Review under the task author/implementer's agent label | Rejected |
| Complete without submitted evidence | Rejected |
| Complete major work without a current approved result | Rejected |
| Change scoped implementation after submission/review | Record and review the changed result again |
| Act with stale maintained or recorded context | Refresh, inspect and acknowledge again |

## Research result and negative finding

Put an experiment script, JSON configuration and input manifest in the project. Define the hypothesis and analysis protocol first, then register:

```sh
python -m uados --project . experiment add --session RESEARCH_SESSION \
  --title "Compare a candidate with a baseline" \
  --hypothesis "The prespecified metric improves over the baseline" \
  --command-json '["python3", "experiment.py", "--config", "config.json"]' \
  --config config.json --dataset data/manifest.json --seed 7 \
  --scope experiment.py --cwd .
python -m uados --project . experiment run EXPERIMENT_ID \
  --session RESEARCH_SESSION --timeout 300
```

The process result records operational success or failure and output paths. Refresh and acknowledge the session, analyze the observations in `evidence/analysis.md`, and conclude:

```sh
python -m uados --project . experiment conclude EXPERIMENT_ID \
  --session RESEARCH_SESSION \
  --conclusion "The candidate did not improve the metric in the measured setting; further datasets remain untested" \
  --evidence evidence/analysis.md
```

A valid negative finding stays in the project memory. If the launcher vanished and the ledger still says running, inspect process state and use `experiment resolve` with a recovery reason after execution has stopped. Preserve a separate record for the rerun.

## Drift and recovery

Run `audit`. If only generated projections differ, inspect diagnostics and run `audit --repair`; then audit again. Changed evidence remains an error requiring restored evidence or new validation, not projection repair. A corrupt ledger requires preservation and verified backup recovery.

For a portable copy, use `export` to a new directory outside the project and explicitly include additional dependencies omitted from recorded scopes. Inspect the copy for private data and run its audit before relying on it. External services, restricted data and installed environments must be restored separately.
