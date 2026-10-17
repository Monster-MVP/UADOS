# UADOS project workspace

UADOS keeps a project's decisions, tasks, evidence and handovers inside the project so another human or agent can continue the work. This scaffold supports software, research and hybrid projects. The Python CLI records structured work; the maintained documents explain how the team should carry it out.

Start with `MASTER_AGENT_WORKFLOW.md`, `PROJECT_STATE.md`, `SESSION_HANDOVER.md`, `DEVELOPMENT_LOG.md`, `DECISION_RECORD.md` and `PROJECT_MEMORY/`. Then read the rules for the work you plan to perform.

## Two kinds of project files

The authoritative record is `.uados/ledger.sqlite3`. UADOS commits current state and its hash-chained event together in one SQLite transaction. It generates these readable projections from that record:

- `PROJECT_STATE.md`: objective, mode, phase, work and blockers.
- `DEVELOPMENT_LOG.md`: durable action history.
- `DECISION_RECORD.md`: problems, alternatives, decisions and reasons.
- `SESSION_HANDOVER.md`: the latest recorded stopping point and next actions.
- `PROJECT_MEMORY/tasks.md`, `PROJECT_MEMORY/knowledge.md` and `RESEARCH_MANAGEMENT/experiments.md`: structured tasks, recorded notes and experiment records.
- `PROJECT_MEMORY/session_reports/`: issued Understanding Reports.
- `.uados/state.json` and `.uados/events.jsonl`: machine-readable projections.

Do not edit those generated files manually. Use the CLI to change their source record. Write free-form knowledge in `PROJECT_MEMORY/notes/` or maintained policies, and link evidence through tracked actions. `audit --repair` rebuilds projections; it does not repair a damaged ledger or recover missing evidence.

## Navigation

| Location | Purpose |
| --- | --- |
| `MASTER_AGENT_WORKFLOW.md` | Session initialization, execution and handover |
| `PROJECT_MEMORY/` | Architecture, tasks, durable notes and lessons |
| `ENGINEERING_RULES/` | Software, quality, security and extension policies |
| `MULTI_AGENT_SYSTEM/` | Roles and independent adversarial review |
| `RESEARCH_MANAGEMENT/` | Hypotheses, experiment records, data and publication |
| `VERSION_CONTROL/` | Git, evidence retention and optional CI/release practices |
| `AUDIT/` | Consistency checks and recovery |
| `TEMPLATES/` | Reusable task, ADR, review and research records |
| `PROMPTS/` | Agent entry and execution instructions |
| `EXAMPLES/` | Worked workflows with expected outcomes |

## Start a session

Run from an environment with UADOS installed, replacing `AGENT_ID` with the team's stable label for the current contributor:

```sh
python -m uados --project . session start --agent AGENT_ID
```

Read the Understanding Report, verify it against the project files, and acknowledge the session using the session ID and report hash printed by the CLI:

```sh
python -m uados --project . session acknowledge SESSION_ID --report-hash REPORT_HASH
python -m uados --project . status
python -m uados --project . context
```

Pass `--session SESSION_ID` to tracked work commands. If another contributor changes recorded work or maintained context, refresh the session, read the replacement report and acknowledge its new hash before proceeding.

UADOS operates in a trusted local workspace. It checks its own tracked commands, but cannot prevent an editor from changing a file or prove that an agent read a document. Agent labels support ownership and distinct-reviewer checks; they do not authenticate people or models. External authentication, protected branches, secret storage, CI and deployment are team integrations, not services provided by this scaffold.

## Adoption and portability

For an existing repository, initialize with `init PATH --name ... --objective ... --mode ... --adopt`. Adoption preserves colliding maintained files such as an existing README or AGENTS instructions and reports `preserved_files`; inspect and integrate their content with this workflow. Existing generated-state collisions remain an error. Initialization without adoption refuses collisions, and neither form silently replaces maintained instructions.

`export PATH` creates an initialized portable directory at a new destination outside the project. It includes the ledger, maintained/generated memory and recorded scopes, evidence and experiment inputs/outputs. Repeat `--include PATH` for additional project-relative dependencies. Inspect privacy-sensitive content before sharing; installed environments and external resources may need separate restoration.

After a Git clone that contains consistent `.uados/events.jsonl` and `.uados/state.json` but no local database, use `python -m uados --project . rebuild-ledger`, then audit. Reconstruction validates exported history and only creates a missing database. It does not overwrite a current ledger or authenticate the exported record. See `VERSION_CONTROL/README.md` for what must be versioned together.

## Project mode

Initialization with `--mode auto` looks for software signals such as source files or package manifests, and research signals such as notebooks, bibliography/LaTeX files or experiment/dataset directories. Both signals select hybrid; research alone selects research; software or an empty project selects software. The empty-project choice has low confidence. Inspect the recorded detection evidence in `PROJECT_STATE.md`; explicitly choose `--mode software`, `--mode research` or `--mode hybrid` during initialization when the heuristic does not reflect the intended workflow. Detection is a starting classification, not a scientific assessment or automatic reclassification after every edit.
