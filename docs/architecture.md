# UADOS v1.0 Phase 2 architecture

UADOS is a dependency-free Python 3.9+ local operating framework for project memory, acknowledged context, owned tasks, adversarial review, recorded experiments and protocol-versioned governance. It provides executable workflow gates and reusable maintained policies. It does not provision a hosted orchestration, authentication, CI or deployment service.

## Components

| Component | Responsibility |
| --- | --- |
| `src/uados/cli.py` | Argument parsing, JSON outputs and process exit codes |
| `src/uados/project.py` | Initialization, mode detection, sessions, tasks, reviews, decisions, audit, export and reconstruction |
| `src/uados/storage.py` | Canonical hashing, SQLite authority, stable OS lock, atomic projection writes and project-relative evidence paths |
| `src/uados/context.py` | Markdown views, context manifest, Understanding Reports and fingerprints |
| `src/uados/research.py` | Experiment registration, provenance, execution, recovery and interpretation |
| `src/uados/protocol.py` | Workflow version, common runtime constants and Phase 2 projections |
| `src/uados/orchestration.py` | Capability registry, role generation/selection, dispatch packets and staged debate/consensus |
| `src/uados/governance.py` | Evidence-backed plans, change requests, research/novelty records and proposed improvements |
| `src/uados/assets/` | Maintained project scaffold: rules, memory guide, templates, prompts and examples |

Both `python -m uados` and the installed `uados` entry point dispatch to the same implementation. A source checkout can also use `python3 scripts/uados.py` without installation. `--project ROOT` precedes the command. Tracked-work operations take a session ID; read-only status/context operations do not. Initialization detects scaffold collisions; explicit `--adopt` preserves existing maintained instructions, reports them for integration and still rejects generated-state collisions.

## Authoritative state and projections

`.uados/ledger.sqlite3` contains one current-state row and an ordered event table. Each event records sequence, UTC timestamp, kind, actor label, summary, previous hash, complete resulting state and its SHA-256 hash. Canonical JSON uses stable key ordering and separators. A loader verifies SQLite consistency, contiguous sequences, every link/hash and equality between current state and the final event's state.

A mutation holds the stable project lock, begins an immediate SQLite transaction, verifies the existing record and generated views, checks workflow gates, applies the operation and commits the event plus current state together. The transaction is the durability boundary. After commit, UADOS updates generated files while retaining the same OS lock.

Generated Markdown, `.uados/state.json`, `.uados/events.jsonl` and session-report files are projections. Each file is written through a temporary file, flushed and replaced atomically; POSIX also synchronizes the parent directory. The group of projection files is not a separate atomic database transaction. If generation fails after commit, the action remains recorded and the CLI tells the contributor not to repeat it. `audit --repair` recreates views from the valid ledger.

The lock's inode is retained. POSIX uses `flock`; Windows uses a byte-range lock. Process exit releases the operating-system lock; a persistent lock file is expected and should not be removed to bypass contention. Locks serialize CLI activity, not arbitrary editor operations. Quiesce external writers when a stable evidence copy is required.

See [ADR 0001](adr/0001-local-ledger.md) for the storage decision and limitations. Full-state events simplify reconstruction but increase storage and verification cost with history; v1 favors transparent local correctness over large distributed histories.

## Context contract

The context bundle combines maintained project Markdown with generated views. Maintained inputs include root README/AGENTS/CLAUDE/workflow, `.agent/` protocols, Cursor wrappers, change policies, project memory, engineering rules, multi-agent policies, research policies, version-control/audit guidance and project `docs/`. Generated reports are excluded from the maintained scan to avoid self-reference. Templates and prompts are reusable supporting assets rather than a substitute for the governed policy files.

Starting a session emits and preserves a structured Understanding Report with objective, phase, architecture, completed work, blockers, risks, resource-document inventory, recommendations, decisions, failures and latest handover. The report has a content hash and records the context fingerprint. Its inventory does not verify hardware or external-data availability; contributors inspect and document those resources.

Acknowledgement must match the current issued report hash and current context. A contributor's own successful tracked mutation advances that session's context fingerprint. Other tracked work or maintained-context edits can make it stale; refresh replaces the report and clears acknowledgement until the new hash is acknowledged. Session-start/acknowledgement metadata is excluded from context-visible projections so acknowledgement does not invalidate itself.

This gate applies to CLI actions. It cannot force reading, prevent a direct edit or determine semantic comprehension. Generated-view edits are detected by projection comparison and require inspection/repair before tracked mutations continue.

## Task lifecycle and review

Tasks retain title, description/acceptance criteria, risk, scope, dependencies, author, implementer, owner session, lease, work submissions, evidence and reviews. Claims enforce completed dependencies and same-task ownership; explicit major scope is required. Active claims with overlapping declared paths, including directory/child relationships, are rejected. Scope-less routine tasks cannot provide file-level coordination, and arbitrary editors remain outside lease enforcement. Expired leases require a recorded takeover reason. Closing a session releases its unfinished task ownership and preserves a handover.

Routine completion requires an owned active task, a recorded explanation and unchanged validation evidence/scoped submission. Major tasks additionally require a current independent plan approval before claim and a current independent result approval before completion.

Review fingerprints include task specification, relevant engineering/multi-agent policy and scoped file snapshots. Result fingerprints additionally include submission revision, work and evidence. The review identity must differ from author and implementer. Evidence and current scope must remain consistent; new content requires renewed submission/review. The human team supplies an actually independent reviewer: agent labels do not authenticate identities.

Decisions preserve problem, at least two alternatives, selected action, reason, evidence and risk. A significant decision linked to an owned major task remains proposed until the independently reviewed task completes. Notes preserve technical explanations, lessons, failures and research reasoning without inventing a second source of task state.

## Research execution

An experiment records hypothesis, nonempty JSON argument array, configuration and dataset fingerprints, seed, required code scope and working directory. Before execution, the runner checks inputs and collects scoped hashes, optional Git revision, launcher Python/platform/package metadata and selected runtime environment variables. The seed is metadata; the invoked program must apply it. If a command launches a different interpreter or container, its environment needs its own emitted provenance.

The runner records durable execution intent, releases the lock, executes without an implicit shell, captures stdout/stderr and finalizes status/output evidence afterward. Other contributors can work while it runs. A successful process whose recorded inputs or scope changed during execution is invalidated. Timeouts and failures remain records. POSIX timeout cleanup addresses the process group; platform limitations must be considered for more complex subprocess trees.

Finalization resolves already recorded execution intent even if another contributor changed context during the run. The launcher session refreshes and acknowledges before subsequent tracked work. An orphaned `running` record is recovered with `experiment resolve` after the contributor inspects actual process state; the command records recovery and does not discover or terminate arbitrary processes. `experiment conclude` stores scientific interpretation and analysis evidence separately from operational exit status.

The runtime does not infer correct design, data completeness, statistical validity or novelty. Maintained research policies govern these responsibilities.

## Portability and recovery

`export PATH` requires a new directory outside the project. Under the project lock it copies a consistent SQLite backup, generated and maintained memory, recorded scopes/evidence/input/output artifacts and optional repeated `--include PATH` project-relative dependencies. The result is itself an initialized local project. It is a reproduction/context packet rather than an exhaustive image of the machine: unrelated files, external data, services and installed environments may need separate restoration.

For Git, preserve consistent `.uados/events.jsonl`, `.uados/state.json`, maintained/generated documents and required evidence. Keep the local SQLite database and lock out of normal text merges. After a clone without the database, `rebuild-ledger` validates the exported chain and state, reconstructs a missing database and regenerates projections. It never overwrites an existing ledger. Divergent event chains cannot be reconciled by concatenating or casually merging JSON lines; select a consistent history and record reconciliation work explicitly.

Audit distinguishes projection drift, missing/changed evidence, recorded warnings and ledger corruption. Repair is limited to projections. Missing/corrupt authoritative records need a validated reconstruction or trusted backup; missing evidence needs restoration or new validation. Fingerprints are local consistency evidence, not authenticated signatures against a trusted external anchor.

## Trust boundary

All collaborators are trusted local writers. The CLI's path rules reject project escapes and symlinked recorded resources, but experiment programs run with the user's privileges. Task leases are not a sandbox. A writer able to rewrite the whole database can also recompute its hash chain. Stronger identity, nonrepudiation, access control, external anchoring and distributed coordination require additional systems and an explicit future design.

## Contributor history and independent review

Claiming a task preserves the contributor identity across handovers. A task author or any current or previous implementation contributor cannot supply its independent plan or result approval. Changing sessions or handing implementation to another agent does not erase that conflict of interest. Reviewer labels still require trusted human attribution.


## Phase 2 governance boundary

Workflow protocol version is independent of SQLite schema version. Schema 1, the single transactional state/event authority and existing full-state events remain intact. Fresh initialization defaults to protocol 2. An explicit upgrade is recorded through an owned, independently planned legacy major task; its historical tasks retain their protocol and approvals. Old evidence, events and contributor history are not rewritten to simulate new compliance.

Protocol-2 tasks add a durable implementation/validation plan with evidence. Major tasks add a seven-field change request, at least two alternatives, generated role coverage and plan/result debates alongside independent plan/result approvals. The task's recorded protocol selects its gates. Missing protocol in historical state means the legacy interpretation, not an automatic migration.

Role generation is deterministic and uses project mode, task text and explicit task-type override. Task risk selects lifecycle depth rather than the role-generation heuristic. Registered capabilities are declarations. Selection covers roles with explicit contributor ownership and at least two eligible independent reviewers; roles may be combined transparently but one label cannot count twice toward independence. A provider-neutral dispatch packet carries task/context/instructions. The local framework does not invoke model providers or establish real independence.

Debates progress through independent analysis, adversarial challenge, votes and consensus. Each participant analyzes and challenges another participant; contribution records and round inputs are immutable. Consensus identifies an actual analysis, rejected alternatives, remaining risks and participant votes/challenges. Task/source/policy/evidence and assignment/capability fingerprints bind the proposal; result debate additionally binds submitted work. Generated consensus must not enter its own input hash. Stale inputs require renewed review, and dissent remains visible.

The research registry adds identified literature sources with truthful full-text/abstract/unavailable access, seven-field ideas and separate falsifiable hypotheses linked to experiments. Candidate novelty is provisional, requires at least two distinct full-text sources from distinct corpus groups plus coverage evidence, and needs an independent substantive audit. Overlap and inconclusive outcomes are preserved. A full-text flag does not establish search completeness, a valid experiment or publication acceptance.

Normal audit remains read-only. Explicit recording deduplicates proposed improvement records with problem, root cause (including unknown), improvement, implementation status and future prevention. It does not execute proposed fixes. Projection repair remains bounded to rebuilding views from valid authority.

Additional generated views are `CONSENSUS_DECISION.md`, `SYSTEM_IMPROVEMENT_LOG.md`, `MULTI_AGENT_SYSTEM/role_plans.md`, `CHANGE_REQUESTS/CR*.md` records, and research gap, novelty, decision and hypothesis registers. The maintained `CR_TEMPLATE.md` is not a generated change record. Generated files are excluded from maintained-policy fingerprints and ordinary source scope snapshots to avoid self-reference, but checked as projections by audit.

## Agent entry and recovery

`MASTER_AGENT_WORKFLOW.md` remains the single lifecycle authority. Root AGENTS and CLAUDE entry files and the actual Cursor `.mdc` wrapper refer to it. `.agent/` protocols provide operational worksheets; `.agent/compatibility.md` records official loader documentation and its limits. Referenced documents must be opened explicitly where the client does not import them. Compatibility files and hidden protocol directories are packaged scaffold assets and governed context inputs.

UADOS supports project-record recovery independently of the client. A logical Day 1/Day 30 identity-switch scenario validates reconstruction of decisions, status and remaining work; it is not evidence of elapsed wall-clock days or execution inside each named commercial product. Those integrations need their own real invocation evidence.

See [ADR 0002](adr/0002-phase2-governance.md) for the additive design and alternatives. Accepted limitations remain local cooperative identity, no OS sandbox, no distributed scheduling/consensus, no authenticated external hash anchor and full-state history growth. Verify hosted OS/CI and native-client results before expanding platform claims.


## Evidence snapshots and audit scope

New evidence registration reads exact bytes once and stores an immutable content-addressed copy under `.uados/evidence/sha256/`. Live approval gates validate both the referenced source path and its promised snapshot: retaining an original does not authorize an edited current input. Existing objects are verified and never overwritten. Orphan objects from rejected transactions are harmless unreferenced residue. Archive paths are excluded from implementation scope and retained in export and Git reconstruction.

Audit reports `ok` for current task/governance bindings and all promised snapshot integrity, and separately reports `history_ok`, `archived_originals` and `historical_evidence_drift`. Superseded records remain visible and are inspected across the event history. If old evidence predates snapshots and its original bytes have been overwritten, audit reports an unrecoverable historical warning rather than inventing a replacement. An unavailable or corrupt promised snapshot is an integrity error. A passing current audit does not mean every legacy original was preserved.
