# UADOS 2.1.0 Independent Adversarial Re-Review (2026-10-26)

Reviewer: dedicated general-purpose subagent, independent of the f3730b5 implementation (73 tool calls, 12 experiment groups, ~21 min). Repository untouched; experiments in /tmp; production ledger only read-only audit (ok=true, 841 events, 179 records).

## Findings

- **F1 [P1] Same-second double compact silently overwrites backups, losing original bytes.** `Project.compact` derives the backup stamp at second precision and copies with unconditional overwrite. Two compacts within one second (natural retry or scripted loops) put the first compact's output into the same-named backup; the only copy of the original 3GB-class ledger/journal is destroyed without warning. Deterministic reproduction with a frozen clock confirmed `original recoverable from backups: False`. Violates the CLI help promise "original bytes are preserved in timestamped backups".
- **F2 [P2] Malformed/partial legacy session state crashes every CLI command with a raw KeyError and cannot self-heal.** A `reports` entry missing `path`/`hash` makes `status`, `audit` (even `--repair`) and `compact` die with tracebacks because `cli.main`'s except tuple excludes KeyError/TypeError. Pre-existing projection_map gap, but compact-as-migration makes it likelier. Requires non-normal data, hence P2.
- **F3 [P3] Projection failure after the compact ledger swap exits 2 with the raw OSError and no "ledger already committed" guidance**, unlike mutate's actionable message; retrying compact walks the user into F1's same-second window.
- **F4 [P3] Compact silently launders a tampered journal.** Tampered events.jsonl → audit exit 1 (drift) → compact exit 0 → afterwards audit ok=true, drift=[], no warning; the tampered bytes move into the backup and are no longer covered by any check. Mutate refuses on drift; compact does not check.
- **F5 [P3] With events.jsonl missing, compact's return value claims a backup_journal that was never created** (flag evaluated after write_projections rebuilt the journal).
- **F6 [P3] Pre-compaction SSHSIG checkpoints fail verification entirely** ("project or sequence is missing"), while the compact docstring promises they "become historical prefixes" — the project id changes, so even prefix verification is impossible. Detectable but unattributable.
- **F7 [P3] Compact memory is O(rewritten total)** (rows fully materialized; ~2.2x journal on a 40MB probe vs 0.6x for streaming status). One-shot migration tool; production ledger already compacted.
- **F8 [P3] harvest_fingerprint is insertion-order sensitive for equivalent evidence sets** — direction is benign (extra snapshots, never missing ones; sha256 collision would be required to lose coverage); normal next_id workflows never reorder dicts.

Observations (not defects): 2MB note bodies cannot pass CLI argv (E2BIG, OS limit); ~40x state RSS amplification per mutation with 2MB states; no Python 3.10+ syntax found.

## Attack surface verdicts

| Surface | Verdict |
|---|---|
| 1 compact failure paths | **Broken (F1, F3)** — six injected failure stages left no half-written DB/lock leaks/temp files and were recoverable via audit --repair, but same-second double compact overwrote backups (naturally triggered once), and post-swap failure reporting misleads. |
| 2 Concurrency | **Held** — concurrent session starts produced distinct sessions with audit ok; note+audit and note+compact serialized correctly via flock; 20 parallel status calls all succeeded. |
| 3 state["compaction"] interactions | **Held** — export→rebuild→audit, adapter, context, coordination benchmark, dispatch run/verify, research idea/source, full v1 upgrade flow all passed; all_evidence safe on unknown keys. |
| 4 Large-object boundaries | **Held** — 2MB note + 40 evidence files through refresh→ack→record→complete→audit→compact→export→rebuild→audit all succeeded, peak RSS ~100MB, steps <0.2s. |
| 5 Harvest fingerprint stability | **Broken, benign (F8)** — order-sensitive fingerprint causes redundant snapshots only. |
| 6 CLI exit codes/--help | **Partially broken (F3, F5)** — success/uninitialized/drift errors otherwise clean; --help accurate. |
| 7 Other | **Broken (F2, F4, F6, F7)** as itemized. |

## Remediation (same day)

- F1: backups now created with O_CREAT|O_EXCL and microsecond stamps; same-second retries produce distinct backup pairs (no overwriting), and an existing backup path aborts compact with an explicit error.
- F4: compact now checks projection/journal drift first and refuses, matching mutate ("run audit --repair"); this also closes the F5 hole (missing journal is drift).
- F3: post-swap projection failure raises an actionable "Ledger compacted...; run audit --repair" message including backup names.
- F5: backup_journal reported only when actually created; a missing journal now refuses compact as drift.
- F6: compact docstring states the true semantics (pre-compaction external anchors no longer verify at all; re-anchor after compaction).
- F2: cli.main additionally converts KeyError/TypeError into clean JSON errors (exit 2).
- F7/F8: accepted as disclosed limitations (one-shot tool memory; order-sensitivity is redundancy-only).
- Regression tests added: same-second double compact keeps distinct backup pairs with intact bytes, O_EXCL refusal on an existing backup, compact refuses projection drift and missing journal, post-swap failure message with repairable state, CLI clean error on malformed session state; test_storage_streaming's hard-coded event-818 hash anchor (invalidated by the documented compaction rehash) replaced with structural chain invariants. Full suite: 147 passed.
