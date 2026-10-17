# Phase 3 recursive evidence plan (T000008)

## Problem and bounded outcome

Phase 2 evidence registration snapshots a supplied file, but a JSON manifest's referenced files remain opaque. Phase 2 and T7 release/validation manifests required manual nested hash checks. Add an explicit, versioned dependency contract through small existing evidence hooks; preserve the SQLite/event authority, schema 1, protocol 1/2 interpretations and ordinary evidence behavior. This is local consistency and retention, not remote access control, global freshness or scientific authenticity.

## Contract

Only new evidence registrations ending in `.uados-manifest.json` opt in. Other JSON remains opaque, including old historical records; never reinterpret old registered bytes. The strict UTF-8 JSON object has exactly `format: uados-evidence-manifest`, integer `version: 1`, and `files`, a nonempty list of exact entries `{path, sha256, bytes, kind}`. `kind` is `file` or `manifest`; manifest entries must use the reserved suffix and file entries must not. Paths are canonical project-root-relative POSIX file paths, with no absolute path, empty segment, dot/traversal, backslash, symlink, generated projection, `.git` or `.uados` dependency. SHA256 is lowercase hex, bytes is a nonnegative integer (not bool). No duplicate keys, nonfinite numbers, unknown fields or implicit glob/directory expansion.

Recursively traverse declared manifests, reject cycles and conflicting declarations, deduplicate shared identical nodes and produce a deterministic sorted closure. Bound depth to 16, unique nodes to 4096, each manifest to 1 MiB and all captured file bytes to 128 MiB. These are local ingestion limits, not a production throughput claim. Read each file once; hash and snapshot the same captured bytes. Validate the complete graph and declared hashes/sizes before publishing any new snapshot. Existing project locking coordinates CLI writers; arbitrary OS edits are not an atomic filesystem snapshot. Later gates recheck live bytes.

Store a new root evidence record's normal path/hash/bytes/snapshot plus `manifest_version: 1` and a flat sorted `dependencies` list of normal evidence records for every transitive node except the root. This avoids losing closure when experiment config uses `[0]`, without changing persistent schema or old evidence records. Both nested manifest bytes and leaf bytes receive immutable content-addressed snapshots. Failure before ledger commit may leave unused valid snapshot objects; no partial evidence record/event may commit. Snapshot publication retains existing flushed exclusive-link behavior.

Validate archived manifest declarations against the stored closure as well as every member snapshot; reject omitted/extra/conflicting dependencies and malformed record shape. Live evidence validation checks every captured dependency. Historical audit validates promised closure snapshots separately from live drift and keeps legacy original-loss semantics. Extend evidence traversal to include root records and their dependencies. Export includes all declared live dependencies and archived originals, rejects current dependency drift/corrupt promised snapshots, and reconstructs unchanged history. Gate integration uses existing `evidence_files`, `check_evidence`, audit, task/research and export paths; do not introduce a second lifecycle.

## Scope and alternatives

New `src/uados/manifests.py`, targeted hooks in storage/project/protocol, new meaningful tests and docs. No CLI command needed: existing repeated evidence arguments and experiment config/dataset registration accept opt-in manifest paths. Preserve old hook behavior for ordinary files. No changes to trust.py or T7 frozen artifacts.

Alternatives: retain manual nested verification (weak transitive gates); flatten every dependency as separate top-level records (loses singular config closure); add a new registry/schema (unnecessary migration); use explicit optional dependency metadata with existing snapshots (selected). Roll back source through a new reviewed task; once dependency records exist, an older runtime cannot enforce their stronger contract and must not be used to approve them. Export/rebuild with the matching runtime remains supported; no fabricated downgrade compatibility.

## Validation and acceptance

Real nested graph and shared-leaf snapshots; exact binary bytes; malformed schemas, duplicate JSON keys, cycles/conflicts, reserved-kind mismatch, canonical path/traversal/symlink/generated inputs, byte/count/depth limits; invalid graph creates no snapshot or event. Leaf-only mutation with unchanged manifests rejects plan claim/review completion and experiment execution/conclusion; current audit fails even if snapshots exist. Historical superseded graphs retain archived originals and corrupted/removed child snapshots fail audit. Export includes out-of-scope dependencies and old archived versions, current drift refuses export, and rebuilt project has identical chain/current audit. Ordinary legacy JSON remains opaque. Real CLI registration/exit codes and two independent reviewer probes, full existing 91 tests and scaffold. Preserve each failure and use new versioned evidence paths. Independently review plan and submitted result via protocol-2 rounds before claim/completion.

## Prior increment

T7 completed at event411 after D5 plan and D6 result consensus with actual independent reviewers. Root final91 tests and independently91 tests passed; current audit at event410 passed, history_ok=false/four old losses retained. T7 implementation artifact's 15-second operation wording means only OpenSSH subprocess timeout, not audit/lock duration; D6 preserved this clarification. Baseline report requested by user remains AUDIT/phase3-baseline-report.md.
