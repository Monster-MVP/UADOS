# Master agent workflow

The project record must be sufficient to resume work without the previous agent's conversation. Use the lifecycle below for human and agent contributors. The CLI enforces the recorded lifecycle; contributors remain responsible for honest records and ordinary filesystem work.

## 1. Establish context before action

Read in this order:

1. This workflow and the project's `AGENTS.md`.
2. `PROJECT_STATE.md` and `SESSION_HANDOVER.md`.
3. `PROJECT_MEMORY/README.md`, architecture, current tasks and relevant notes.
4. `DEVELOPMENT_LOG.md` and `DECISION_RECORD.md`, focusing on the planned area.
5. Relevant `ENGINEERING_RULES/`, `RESEARCH_MANAGEMENT/` and `MULTI_AGENT_SYSTEM/` documents.
6. Task evidence and relevant implementation or data; a summary alone is insufficient for a risky change.

Start a session:

```sh
python -m uados --project . session start --agent AGENT_ID
```

Inspect the printed Understanding Report. It should describe the objective, phase, architecture context, completed work, current problems, risks, resources and recommended next actions. Check those statements against their underlying files. Add an explicit assumption or blocker when the record is incomplete; do not infer success from absent data.

The report includes its hash. Acknowledge the report you actually inspected:

```sh
python -m uados --project . session acknowledge SESSION_ID --report-hash REPORT_HASH
```

Acknowledgement is a traceable assertion by the contributor, not proof of reading. CLI work commands require a currently acknowledged session. When context changes, run `session refresh SESSION_ID`, inspect the replacement report and acknowledge its replacement hash. Policy changes, extension rules and other contributors' recorded work can make an older context stale.

## 2. Define owned work

Create a task with its purpose, completion criteria, risk, relevant file scope and dependencies:

```sh
python -m uados --project . task add --session SESSION_ID \
  --title "Describe the observable outcome" \
  --description "Problem, acceptance criteria and validation plan" \
  --risk routine --scope src/component
```

Repeat `--scope PATH` and `--depends TASK_ID` as needed. Choose `major` when the change materially affects architecture, security, public behavior, data integrity, research validity or cost. Do not split a major decision into nominally routine tasks to avoid review.

For major work, record the plan as a maintained artifact using `TEMPLATES/rfc.md` or `TEMPLATES/task.md`. Have an independent reviewer challenge the plan and record a `plan` approval before claiming the task. Claim the task with the implementing session. Claims establish recorded ownership and scope leases; overlapping work requires coordination. Dependencies must be satisfied before dependent implementation proceeds.

## 3. Implement and preserve reasoning

Make the smallest coherent change that satisfies the task. Keep implementation, docs and relevant validation together. A tracked task command does not automatically record each editor operation: record important findings explicitly.

Use `decision add` for choices requiring durable rationale: problem, alternatives, decision, reason, evidence and risk. Use `note` for technical explanations, lessons, failed approaches or research observations. Retain the triggering error, configuration and result for failed attempts; a later contributor should understand why repeating the attempt is unhelpful.

If the planned scope or assumptions change substantially, revise the plan and obtain a new review. If work cannot safely continue, use `task block TASK_ID --reason ... --session SESSION_ID` and include a recovery action. Never turn an unavailable resource into a fabricated result.

## 4. Validate and challenge the result

Run meaningful checks for the changed behavior. Preserve their outputs in project evidence files. Record the result:

```sh
python -m uados --project . task record TASK_ID --session SESSION_ID \
  --summary "What changed, why, and what the checks established" \
  --evidence evidence/validation.txt
```

An evidence path should contain readable material that supports the claim. A hash establishes a recorded content comparison; it does not establish scientific truth or the authenticity of a log.

For major work, an independent reviewer inspects the recorded result, scoped files and evidence. Record a `result` review using `task review` with `--verdict approve` or `--verdict request_changes`, a concrete `--challenge`, and supporting evidence. A result approval binds the reviewed task, scoped contents and evidence. Changing those inputs requires renewed approval.

Complete only when the acceptance criteria and evidence are satisfied. Major tasks also need a current independent approved result. Uncertainty that affects completion must remain visible as a blocker, follow-up or limitation.

## 5. Research branch

Research and hybrid projects use the same session and task lifecycle. Before a run, record the hypothesis, command as a JSON argument array, configuration, dataset manifests, seed, working directory and relevant scope with `experiment add`. Execute with `experiment run EXPERIMENT_ID --timeout SECONDS --session SESSION_ID`.

Keep raw outputs and a structured result analysis. Refresh and acknowledge the session after a run, then store the scientific interpretation with `experiment conclude EXPERIMENT_ID --session SESSION_ID --conclusion ... --evidence ...`. Distinguish a failed process, an invalid experiment and a valid negative result. Verify input fingerprints and data access before treating a later run as a replication. See `RESEARCH_MANAGEMENT/` for environment, statistical and publication requirements that the CLI cannot infer automatically.

## 6. Close with a usable handover

At a stopping point, ensure task records, decisions, notes and evidence reflect the actual work. Close the session:

```sh
python -m uados --project . session close SESSION_ID \
  --summary "Completed work and its validation" \
  --next "The first concrete action for the next contributor" \
  --blocker "An unresolved issue, if present" \
  --failed "A failed approach and why it failed, if present"
```

Repeat next actions or failure/blocker fields where supported. Omit optional fields when absent; do not invent a blocker. Use `TEMPLATES/handover.md` to gather details before closing. Include task IDs, file paths, commands, acceptance gaps and the reason for the next action. The next session must verify this handover against current state rather than treating it as a universal guarantee.

## 7. Audit and improve

Run `audit` at handover, before a consequential review and after copying or restoring the workspace. Investigate differences between ledger, projections and evidence. `audit --repair` regenerates projections from the authoritative ledger; it must not erase an inconsistency in evidence or rewrite the ledger's history.

Improve repeated problems through `ENGINEERING_RULES/extensions.md`: document the failure, propose a bounded rule, review it, update maintained policy and verify its practical effect. Preserve the original lesson and the new decision so future contributors can reconsider the trade-off.
