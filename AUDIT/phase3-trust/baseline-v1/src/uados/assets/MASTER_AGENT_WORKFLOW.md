# Master agent workflow

This is the single UADOS lifecycle authority. Product entry files point here; `.agent/` files supply operational guidance, and engineering, research and multi-agent policies specialize evidence and review. Project records must let a contributor resume without the previous chat. CLI gates support this contract but cannot prove comprehension, identity or scientific truth.

## 1. Establish context before action

Read in this order:

1. This workflow and the applicable native agent entry file.
2. `PROJECT_STATE.md` and `SESSION_HANDOVER.md`.
3. `PROJECT_MEMORY/README.md`, architecture, current task, dependencies and relevant notes.
4. `DEVELOPMENT_LOG.md` and `DECISION_RECORD.md` for the planned area.
5. Relevant `ENGINEERING_RULES/`, `RESEARCH_MANAGEMENT/`, `MULTI_AGENT_SYSTEM/` and `CHANGE_REQUESTS/` policies.
6. Scoped implementation, data and evidence underlying the claims; summaries alone are insufficient.

Use the startup guidance in [.agent/startup_protocol.md](.agent/startup_protocol.md). Identify yourself with a stable team label; determine software, research or hybrid mode from recorded detection and actual project resources. Explicitly state missing resources and unresolved assumptions. Inspect existing tasks before creating overlapping work.

```sh
python -m uados --project . session start --agent AGENT_ID
```

Inspect the issued **PROJECT UNDERSTANDING REPORT** and its underlying source files. Check objective, phase, architecture, completed work, problems, risks, resources, decisions, failures and recommended next actions. An inventory of files is not a check that data, hardware or external services are available. Prepare an execution plan before implementation.

```sh
python -m uados --project . session acknowledge SESSION_ID --report-hash REPORT_HASH
```

Acknowledgement must use the exact report hash you inspected. Tracked work requires current acknowledgement. When context changes, run `session refresh SESSION_ID`, inspect the replacement report and acknowledge its new hash. Other recorded work and maintained policy changes can make context stale. Do not bypass a stale-context error with a different label.

## 2. Define and review owned work

Follow [.agent/task_execution_protocol.md](.agent/task_execution_protocol.md): task definition → risk assessment → implementation plan → review → execution → validation → documentation → final audit.

```sh
python -m uados --project . task add --session SESSION_ID \
  --title "Describe the observable outcome" \
  --description "Problem and acceptance criteria" \
  --risk routine --scope src/component
```

Repeat `--scope PATH` and `--depends TASK_ID` as needed. Select `major` for architecture, public behavior, persistent integrity, security/data boundaries, research validity, material cost or other consequential changes. Do not split a major decision into nominally routine tasks to evade review.

Fresh projects use workflow protocol 2. Every protocol-2 task needs a recorded implementation plan, validation plan and evidence before claim. A major task additionally needs a seven-field change request with at least two alternatives, generated roles and completed evidence-bound plan debate/consensus plus independent plan approval. See [change policy](CHANGE_REQUESTS/CHANGE_POLICY.md) and [multi-agent policy](MULTI_AGENT_SYSTEM/README.md). Record the plan using the task ID printed by `task add` and existing readable evidence:

```sh
python -m uados --project . task plan TASK_ID --session SESSION_ID \
  --implementation "Steps, assumptions, alternatives and recovery" \
  --validation "Checks, inputs and expected outcomes" \
  --evidence evidence/plan.md
```

For protocol-2 major work, prepare a project-relative JSON change record using `CHANGE_REQUESTS/CR_TEMPLATE.md`, then use `change propose TASK_ID --record evidence/change.json --session SESSION_ID`. Register contributors with `agent register --capability CAPABILITY --session SESSION_ID`, generate roles with `roles generate TASK_ID --session SESSION_ID`, inspect candidates with `roles select ROLE_PLAN_ID` and explicitly assign them with `roles assign ROLE_PLAN_ID --role ROLE_ID --agent AGENT_ID --session SESSION_ID`. Use the IDs printed by the CLI; examples are placeholders, not existing project records.

Open the plan debate with `debate open TASK_ID --roles ROLE_PLAN_ID --stage plan --session SESSION_ID`. Each contributor obtains a read-only packet with `debate packet DEBATE_ID --agent AGENT_ID`, submits analysis and challenges, votes and records consensus using the exact forms in `MULTI_AGENT_SYSTEM/debate_protocol.md`. Consensus records eligible independent approvals from reviewer votes. `task review` remains available for an additional challenged approval; a standalone report or approval does not satisfy the required debate. Use each operation's `--help` for all required fields.

Legacy protocol-1 tasks retain their recorded gates: an independent challenged plan approval before major claim and an independent challenged result approval before major completion. An explicit `upgrade --session SESSION_ID --task OWNED_LEGACY_MAJOR_TASK_ID` enables protocol 2 for newly created tasks; it does not reinterpret historical tasks or replace ledger history. Never treat a legacy approval as protocol-2 consensus.

Reviewers must independently inspect assumptions, relevant files and evidence. A protocol-2 major debate needs at least two independent reviewers, each outside task author and current/past implementation contributors. Distinct labels alone do not establish independent people or models. Assign coverage using declared capabilities and record who actually performs each role.

Claim the task in the implementing session only after required planning, dependencies and approvals are satisfied. Active leases reject overlapping declared scopes, including ancestor/descendant paths. Paths describe ownership and review scope, not an OS sandbox. Do not overwrite active work. Coordinate outside-scope changes, revise scope/plan as appropriate, or record a blocker and a recovery action when ownership, authority or resources prevent progress.

## 3. Execute and preserve reasoning

Make the smallest coherent change satisfying the approved task. Keep implementation, documentation and meaningful validation together. Editor operations are not automatically logged; record important findings through the CLI.

Use `decision add` for durable rationale: problem, alternatives, decision, reason, evidence and risk. Use `note` for technical explanations, lessons, failures or research observations. Preserve rejected approaches with their trigger, command, inputs and observed result. If scope or assumptions change materially, revise the plan and obtain renewed review before dependent execution.

Edit maintained files. Never hand-edit generated `PROJECT_STATE.md`, `DEVELOPMENT_LOG.md`, `DECISION_RECORD.md`, `SESSION_HANDOVER.md`, `CONSENSUS_DECISION.md`, `SYSTEM_IMPROVEMENT_LOG.md`, `PROJECT_MEMORY/tasks.md`, `PROJECT_MEMORY/knowledge.md`, `PROJECT_MEMORY/session_reports/`, `MULTI_AGENT_SYSTEM/role_plans.md`, `CHANGE_REQUESTS/CR*.md` records (except the maintained `CR_TEMPLATE.md`), `RESEARCH_MANAGEMENT/experiments.md`, `RESEARCH_MANAGEMENT/NOVELTY_AUDIT.md`, `RESEARCH_MANAGEMENT/LITERATURE_GAP_ANALYSIS.md`, `RESEARCH_MANAGEMENT/RESEARCH_DECISION_RECORD.md`, `RESEARCH_MANAGEMENT/HYPOTHESES.md`, `.uados/state.json` or `.uados/events.jsonl`. Record free-form durable knowledge under `PROJECT_MEMORY/notes/` or with `note`; follow [.agent/memory_update_protocol.md](.agent/memory_update_protocol.md).

## 4. Validate and challenge the result

Run checks proportionate to risk. Evidence must include the exact command or procedure, relevant inputs/environment, exit status, material results, failures and limits. Do not describe unexecuted checks as passing or unavailable sources as empty results.

```sh
python -m uados --project . task record TASK_ID --session SESSION_ID \
  --summary "What changed, why, and what validation established" \
  --evidence evidence/validation.txt
```

For protocol-2 major work, open a result debate with `debate open TASK_ID --roles ROLE_PLAN_ID --stage result --session SESSION_ID` over submitted current work. Complete its rounds so consensus records current independent result approvals from eligible reviewer votes. For legacy major work, use the recorded independent result-review gate. Review approval must include a concrete challenge and readable evidence. Task, scope, policy, source, role assignment, declared capability and evidence changes can stale the relevant approval or consensus; renew the required records instead of relabeling or dropping dissent.

Run a final audit. Complete only when acceptance criteria, unchanged evidence and all applicable current approvals are satisfied. If important uncertainty remains, record a blocker, owned follow-up or explicit limitation. Hashes establish content consistency, not authenticity or proof that the conclusion follows.

## 5. Research branch

Apply the same lifecycle in research and hybrid projects. Follow [innovation policy](RESEARCH_MANAGEMENT/innovation_policy.md), reproducibility, data-management and publication rules. Register literature with stable source identifiers and truthful `full_text`, `abstract` or `unavailable` access. Capture search coverage and exclusion reasons; unavailable access does not show absence of prior work.

Record research ideas with existing work, current limitation, scientific gap, proposed innovation, why prior methods cannot solve it, expected contribution and publication potential. Register a separate falsifiable hypothesis: prediction, rejection criterion and testing method. Protocol-2 scientific experiments link the idea and hypothesis records; explicitly operational-only executions may omit a hypothesis and cannot support a scientific outcome. A provisional candidate novelty verdict needs at least two distinct full-text sources, coverage evidence and an independent evidence-backed audit. Preserve `overlap` and `inconclusive` outcomes; no verdict proves global novelty or publication acceptance.

Before a run, register an explicit JSON argument vector, configuration, dataset manifests, seed, working directory and relevant scope with `experiment add`. Inspect the invoked program and use `experiment run EXPERIMENT_ID --timeout SECONDS --session SESSION_ID`. Programs run with the user's privileges; seed metadata does not cause the program to apply it.

Keep raw output and structured analysis. After execution, refresh and acknowledge, then record scientific interpretation with `experiment conclude`. Distinguish process failure, an invalid experiment, a valid negative finding and an inconclusive result. Verify input/environment availability before a replication claim; contributors supply validity and statistics that the CLI cannot infer.

## 6. Close with a usable handover

Follow [.agent/handover_protocol.md](.agent/handover_protocol.md). Update task records, decisions, notes and evidence, then close the session so UADOS generates `SESSION_HANDOVER.md`.

```sh
python -m uados --project . session close SESSION_ID \
  --summary "Current status, completed work and validation" \
  --next "First concrete next action with task/evidence paths"
```

Add repeatable `--blocker` and `--failed` fields when real issues exist. Preserve remaining tasks, known problems, important decisions, failed approaches and recommended next actions. Close releases unfinished task leases while retaining contributor history. A new contributor must verify the handover against current files and ledger rather than assuming old resources remain available.

## 7. Audit and improve

Run `audit` before consequential review, at handover and after copying/restoring a workspace. Its normal operation is read-only. `audit --repair` regenerates projections from a valid ledger; it does not repair evidence, change scientific conclusions or erase history. `audit --record --session SESSION_ID` can create deduplicated proposed improvements in `SYSTEM_IMPROVEMENT_LOG.md`; it does not automatically execute a fix. Diagnostic audit recording may use an already acknowledged session whose context has since become stale, because it authorizes no implementation; refresh is still required before tracked work.

An improvement records problem, root cause (or explicitly unknown cause), proposed improvement, implementation status and future prevention. Follow `ENGINEERING_RULES/extensions.md` to turn it into owned, reviewed, validated work. Preserve original failures and lessons. Stronger external identity, provider dispatch, distributed coordination and authenticated audit anchors require separate integrations.


For a manually investigated improvement, `improvement --record evidence/improvement.json --session SESSION_ID` accepts string fields `problem`, `root_cause`, `improvement`, `implementation`, `prevention` and an `evidence` array of readable project-relative paths. State an unknown root cause explicitly. The record remains proposed work; implement a fix through its own task and review process. Use `adapter --runtime Codex --agent AGENT_ID` (or the CLI's other runtime choices) to obtain a read-only bootstrap/context packet, not to launch the named client.


Record validation results to a new, versioned artifact path. Never overwrite a file after a task, review, change, experiment or debate has referenced its bytes; record a new result and obtain the required current review. UADOS archives exact registered bytes, but current-path drift still invalidates active approvals. Audit distinguishes current consistency from historical original-byte availability; inspect both `ok` and `history_ok`, and preserve reported historical loss honestly.
