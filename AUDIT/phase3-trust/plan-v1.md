# Phase 3 trust foundation plan (T000007)

Extend the verified local ledger, without schema/protocol replacement, with optional OpenSSH SSHSIG checkpoint signing and externally authorized verification. This is the first Phase 3 increment, not a claim that all production/distributed/provider requirements are complete.

## Design

A new `uados.trust` module and thin CLI `trust checkpoint`/`trust verify` commands use `ssh-keygen -Y sign/verify` with fixed domain-separated namespace `uados-checkpoint@uados.local`. A canonical JSON payload binds format/version, signer principal, first-event project ID, event sequence/head hash, full-state digest, and audit current/history results. No private key or trusted signer policy is stored in project memory, scopes, evidence or exports. Signing keys, authorization/revocation files and detached checkpoint bundles are operator-supplied external paths; filenames/output directories are new and never overwritten. Tests generate disposable keys outside fixture projects and remove them afterward.

Checkpoint creation holds the existing project lock for a consistent ledger+audit snapshot, checks projection/current-integrity failures, serializes canonical bytes, signs with an explicit external private key (no implicit shell, no hidden provider), and publishes a new external directory containing checkpoint.json and checkpoint.json.sig only after signing succeeds. Bound subprocess runtime. Signature success alone is not identity enrollment: signer's principal must be verified against the separately supplied allowed-signers policy. No checkpoint event is appended, avoiding self-referential head changes.

Verification requires the caller's expected checkpoint SHA256 from a trusted external source, signer principal and external allowed-signers policy, optionally OpenSSH revocations. Reject malformed/oversized data, missing executable, timeout, unauthorized signature/key/principal, wrong namespace, path aliases/symlinks and missing detached signature. Verify the signature before trusting payload claims; then check first-event identity, event-sequence/head, and exact state at that event in the already chain-validated ledger. A historical-prefix checkpoint does not cover later events: report it explicitly, and `--require-current` rejects a non-current head. The caller's pinned digest prevents silent checkpoint substitution/rollback; UADOS cannot secure an attacker-controlled external pin or public-key policy.

Verification independently compares recorded checkpoint state/audit claims to the bound event and reports the *current* audit separately. Signed loss findings preserve Phase 2 history_ok=false rather than replacing missing bytes. External signature checks do not authenticate local agent labels or retroactively sign each event, and mutable live evidence/current audit may drift after an old checkpoint.

## Alternatives and tradeoffs

1. Keep only cooperative SHA256 hashes: simplest but local rehashing can forge the whole chain.
2. Implement cryptography in stdlib/pure Python: dependency-free but unsafe maintenance burden and new crypto correctness risk.
3. Add cryptography package/hosted identity service: richer features but new dependency/credential/deployment requirements.
4. Use optional platform OpenSSH SSHSIG boundary: established implementation and principal/namespace/revocation support, explicitly fail unavailable. Chosen for this bounded increment.

## Validation and recovery

Real temporary ed25519 signing/verification and allowed-signers policy (no production key). Test current/historical checkpoints, independent expected pin, rehash-forged ledger, wrong policy/key/principal, namespace mismatch, revoked key, malformed payload, missing executable/timeouts, output overwrite/symlink/inside-project refusal, and preservation of legacy history/zero new events. Full 75 existing tests and scaffold must pass. Preserve immutable Phase 2 evidence/reports; maintained CLI source evolves only under this review. Record all new artifacts under unique Phase 3 paths. If OpenSSH is unavailable, commands fail explicitly and tests report actual skips; optional CLI remains backwards compatible. No remote publication, key enrollment, provider dispatch or network deployment.

## Primary reference

https://man.openbsd.org/ssh-keygen.1 (accessed 2026-10-13): `-Y sign`, `-Y verify`, mandatory namespace, authorized principals and `-r` revocation. Official tool API; actual host behavior must be executed and captured, not inferred from docs.
