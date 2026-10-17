# ADR 0001: One local transactional ledger with rebuildable views

- Status: Accepted for UADOS v1.
- Scope: Project state, durable event history and generated memory.

## Problem

Agents need project knowledge that survives a model change, process interruption or machine handover. Several independently edited Markdown/JSON files cannot establish which state is authoritative or guarantee that a task update and its history entry commit together. A projection failure must not silently erase committed work or cause a contributor to repeat it.

## Alternatives considered

| Alternative | Benefit | Limitation |
| --- | --- | --- |
| Markdown-only memory | Easy manual editing and human review | No transactional state/history boundary or enforceable lifecycle |
| Separate JSON state and append-only JSONL events as authority | Simple portable formats | Cross-file writes can diverge during interruption; concurrent writers need an additional transaction design |
| Hosted database and orchestration service | Central identity and multi-machine coordination are possible | Requires deployment, network, service administration and a broader trust/availability design |
| Local SQLite ledger with generated Markdown/JSON | Standard-library ACID transaction, inspectable record, offline operation | Local writer trust; serialized writes; external filesystem evidence is not transactional database data |

## Decision

Use `.uados/ledger.sqlite3` as the sole runtime authority. Commit an ordered hash-chained event containing the complete resulting state and the current-state row in the same SQLite transaction. Validate chain continuity and equality between final event and current state on reads. Hold a stable OS project lock across transaction and subsequent projection generation.

Generate Markdown views, current-state JSON, event JSONL and session reports from that record. Repair only these projections from a valid ledger. For a project restored from versioned text exports without its local database, provide a separate `rebuild-ledger` command that validates the chain/state and reconstructs a missing database without overwriting an existing one.

## Reason

SQLite is available in Python's standard library, supports a concrete durability boundary and needs no network service. Full-state events retain enough information for straightforward recovery and inspection. Readable projections preserve the user-facing workflow and portability while keeping source-of-truth ambiguity out of ordinary operations.

The stable lock prevents two cooperating CLI writers from committing/generating out of order. Atomic per-file writes prevent truncated projections. Keeping database transactions distinct from derived-file generation lets the system explain an already committed action and repair its views without duplicating the action.

## Evidence and verification

The implementation separates storage, project lifecycle, context rendering and research execution. Workflow tests exercise handover, major-review gates, projection failure/repair, export and validated reconstruction. The current verification report determines which tests were actually run; the architectural choice itself is not evidence that every failure path is covered.

## Risks and consequences

- Full-state event rows consume increasing storage, and complete chain validation costs grow with history. Revisit for very large projects or measured latency problems; do not prune history without an explicit retention/recovery design.
- Scope/evidence files remain outside SQLite. The lock does not stop direct editors, and retained hashes do not restore deleted artifacts. Quiesce uncooperative writers for consistent copies and back up evidence with memory.
- A hash chain is local consistency evidence, not authenticated provenance. A writer controlling the ledger can rewrite it and recompute hashes. External trusted anchors, signatures and identity require a future design.
- Git exports must represent one consistent history. Divergent chains are not safely merged by concatenating JSONL records. Preserve a selected validated chain and explicitly reconcile work.
- Projection repair cannot repair ledger corruption or establish truth from changed evidence. Preserve diagnostics and restore a verified backup or validated missing-ledger export as appropriate.
- Hosted/distributed coordination, stronger access controls and cryptographic authentication are beyond the accepted v1 boundary. Revisit when those become actual requirements.
