# UADOS 2.1.0 Remediation Validation Record (2026-10-25)

Task: T000011 (major, session S000015). Audit basis: `AUDIT/2026-10-25-adversarial-audit/report.md`.

## Commands executed and observed results

1. Full test suite (uv-managed pytest 8.x, Python 3.13.9):
   `PYTHONPATH=src uv run --no-project --with pytest -- python -m pytest tests/ -q`
   → `142 passed, 7 subtests passed in 34.47s` (baseline before change: 135 passed; +7 new format-v2 tests; phase4 benchmark artifacts now written to the test sandbox, repository AUDIT/benchmarks no longer modified by test runs).
2. Python 3.9 compatibility:
   `PYTHONPATH=src /usr/bin/python3 -m compileall -q src/uados` → exit 0 (Python 3.9.6).
3. Production ledger compaction (after full-project copy verification in /tmp/uados-compact-verify):
   `PYTHONPATH=src python3 -m uados --project . compact`
   → previous_events=833, new_events=834, snapshots=135,
     events.jsonl 3,001,036,639 → 27,104,614 bytes (111x),
     state.json 9,050,216 → 754,357 bytes,
     wall 43.8s, peak RSS 355 MB,
     backups `ledger.pre-compact-20261025T120943Z.sqlite3` (3.0GB) and
     `events.pre-compact-20261025T120943Z.jsonl` (3.0GB) retained under `.uados/`.
4. Copy-first verification (identical operation on a full rsync copy):
   pre-compact audit: ok=true, 833 events, history_ok=false (same four disclosed legacy drifts), evidence_records_checked=177;
   post-compact audit: ok=true, 834 events, projection_drift=[], evidence_records_checked=178 (full historical harvest preserved);
   post-compact audit cost: 1.05s wall / 55 MB peak RSS (pre-compact: 73.9s / 3,827,744,768 B);
   post-compact mutation smoke: session refresh + session close + audit ok=true (836 events).
5. Production audit after compaction and stale-session closure:
   `PYTHONPATH=src python3 -m uados --project . audit` → ok=true, event_count=836, projection_drift=[], errors=[].
6. Stale sessions: S000011 and S000012 (active since 2026-10-13, 45/37 embedded reports) closed with honest handover summaries; no task leases were held.

## Contract changes (documented)

- Events since 2.1.0 carry `state_digest`; full state snapshots are embedded only when the harvestable evidence set changes or every 100 events. Legacy full-state events load and verify unchanged.
- `rebuild-ledger` for digest-only journal tails requires `.uados/events.jsonl` plus `.uados/state.json` (both live in `.uados/` and in every export); the journal alone no longer carries the current state for such tails. Test `test_adversarial.py::test_rebuild_restores_missing_state_export_from_complete_history` updated accordingly with an explicit negative case.
- `compact` rehashes the event chain; external trust checkpoints pinning the pre-compaction head become historical prefixes (honest disclosure recorded in the `ledger.compact` event summary and README Q6).
- Rollback from a compacted ledger to 2.0.0 binaries is unsupported (2.0.0 loaders expect full-state final events).

## Known remaining limitations

- The four pre-snapshot Phase 2 evidence originals remain unrecoverable (unchanged, disclosed by history_ok=false).
- `review-bundle create` still records no ledger event (deferred; disclosed in the audit).
- T000011 remains open pending the independent multi-role review the major-task gate requires; this remediation was owner-directed with the independent adversarial audit report as review input.
