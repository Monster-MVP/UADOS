# UADOS Phase 3 Baseline Report

**Inspection date:** 2026-10-13 (Asia/Shanghai)  
**Scope:** read-only architecture, protocol, memory, audit, test and distribution inspection before Phase 3 implementation.  
**Runtime observed:** macOS arm64, Python 3.9.6, dependency-free standard-library runtime.  
**Important record:** starting the required acknowledged UADOS session created the normal `session.start` ledger event S000010; no implementation source or historical evidence was edited during this baseline.

## 1. Current system capability summary

UADOS is a local, provider-neutral R&D workflow framework built around a SQLite authoritative ledger, full-state hash-chained events, generated Markdown/JSON projections, atomic projection writes, stable OS locking, evidence snapshots and rebuildable exports. Fresh projects use protocol 2 while the schema and historical protocol-1 interpretation remain intact.

The current lifecycle is explicit: start and acknowledge an Understanding Report, define scoped work, record implementation and validation plans, obtain risk-proportionate independent review, execute through the CLI, preserve decisions/failures/evidence, run audit, and close with a structured handover. The CLI cannot prove that a contributor read a report, that a declared agent is a distinct person/model, or that a scientific conclusion is valid.

## 2. Implemented functionality

### Core workflow and memory

- SQLite state plus ordered, SHA-256 linked full-state events; current state must equal the last event.
- Stable project lock, immediate transactions, atomic generated projections and projection drift detection/repair.
- Structured session start, Understanding Report hash, acknowledgement, refresh, stale-context gates and generated handovers.
- Task dependencies, explicit scopes, leases, takeover records, contributor history and routine/major completion gates.
- Durable decisions, notes, failed approaches, experiments and exported/rebuilt project records.

### Phase 2 governance and orchestration

- Protocol 2 is additive to schema 1 and preserves Phase 1/legacy event history.
- Seven-field major change requests, implementation/validation plans and generated role plans.
- Capability declarations, explicit role assignments and provider-neutral dispatch packets.
- Three staged debate rounds: analysis, adversarial challenge and vote, followed by consensus binding task/policy/scope/evidence/assignment fingerprints.
- Independent plan/result approval quorum with exclusion of authors and implementation contributors; dissent and rejected alternatives remain historical.
- CLI malformed-input validation, stale-policy invalidation, evidence snapshot creation, current-path checks and historical archive checks.

### Research and audit

- Literature records distinguish full text, abstract and unavailable access; source identifiers and corpus groups are retained.
- Seven-field research ideas, provisional novelty audits, coverage limits and separate falsifiable hypotheses.
- Experiment argument vectors, dataset/configuration manifests, seeds, scoped provenance, timeout/failure/recovery records and exact outcome interpretation.
- Audit separates `ok` from `history_ok`, reports historical evidence drift honestly and checks promised immutable snapshots.
- `audit --record` produces deduplicated proposed improvements; the improvement log does not silently execute fixes.

### Packaging and validation already present

- 48 packaged maintained assets, including hidden `.agent` and Cursor `.mdc` compatibility files.
- Phase 2 acceptance recorded 75 tests, local scenario runs, isolated wheel installation, Git reconstruction and snapshot-aware exports.
- The frozen Phase 2 delivery manifest contains 81 entries and was rechecked in this inspection with zero mismatches.
- The configured CI matrix covers Python 3.9/3.12/3.14 on Ubuntu/macOS/Windows, but hosted runs are not evidence in this local workspace.

## 3. Current state and integrity observations

The ledger currently contains 312 events after the required Phase 3 startup event, 6 completed tasks, 10 sessions, 4 registered agent profiles, 5 role plans, 4 debates, 5 change records and 5 improvement records. There are no literature, idea or hypothesis records in the root project state; research coverage is exercised primarily through fixtures and prior Phase 2 evidence. The local ledger is approximately 338 MB and the JSON state projection approximately 2.6 MB.

The current audit is `ok=true` with no projection or snapshot errors. `history_ok=false` remains correctly reported because four pre-snapshot Phase 2 evidence originals cannot be reconstructed. The 81 frozen Phase 2 files remain byte-identical. This report does not reinterpret those historical limitations as resolved.

The baseline test suite reran successfully: **75 tests in 46.958 seconds**. `scripts/verify_scaffold.py` also passed with 16 required paths, 4 onboarding events in its disposable project and 47 packaged Markdown assets. These are local checks only.

## 4. Missing capabilities

The following gaps are explicit Phase 3 candidates rather than defects hidden by the current audit:

1. **Authenticated identity and signed audit anchors.** Agent IDs, runtime labels and capabilities are cooperative metadata. The local hash chain has no external trust anchor, signature, key rotation or verifier policy.
2. **Provider/native-client dispatch.** Adapters produce context packets but do not invoke Codex, Claude Code, Cursor, Qoder, ZCode or another provider, nor capture a tamper-evident provider receipt.
3. **Protected evidence and release integrity.** Content-addressed snapshots prevent accidental overwrite inside the local project, but access control, encryption, retention, remote object integrity and release attestation are absent.
4. **Hosted cross-platform execution.** The CI matrix is configured but not executed in this environment; Linux, Windows, newer Python, network filesystems and platform-specific lock behavior remain unvalidated.
5. **Distributed coordination and scale.** The stable local lock does not coordinate multiple hosts. Full-state events make history transparent but increase storage and verification costs; the 338 MB local ledger is an early scale signal.
6. **First-class recursive dependency manifests.** Phase 2 manually checked nested evidence for its release. Ordinary evidence registration does not automatically enforce transitive source dependencies after later changes.
7. **Systematic literature integration.** The research registry accepts truthful records, but search/provider adapters, deduplication, retrieval provenance, corpus snapshots and automated coverage reports are not implemented.
8. **Stronger scientific validation.** Fixtures demonstrate bounded mechanics and known-method reproduction; physical data, instrument calibration, non-oracle controls and domain-specific statistical review remain external work.
9. **Release and operations controls.** There is no signed release bundle, migration/version policy beyond the current wheel workflow, metrics/tracing, policy-based retention or recovery drill for remote stores.

## 5. Gap analysis against Phase 3 intent

| Phase 3 intent | Baseline status | Evidence/limit |
|---|---|---|
| Production trust | Partial | Local hash chain, snapshots and audits work; identity and external anchoring absent |
| Intelligent orchestration | Partial | Deterministic roles and debates work; no real provider dispatch or receipt verification |
| Enterprise security | Partial | Path/symlink/input gates exist; no authenticated authorization, encryption or remote policy enforcement |
| Distributed workflow | Local only | SQLite transaction and OS lock are single-project/single-host mechanisms |
| Scalable history | Validated at small scale | Full-state history is transparent; current ledger size warrants benchmark and compaction design |
| Research intelligence | Registry and fixtures | No systematic retrieval/search integration or real-domain scientific validation |
| Portability | Configured, locally tested | Hosted OS/Python matrix remains unexecuted |
| Release confidence | Strong local baseline | Frozen assets, wheel/Git checks and 75 tests pass; no signed release provenance |

## 6. Recommended implementation order

1. **Trust foundation:** introduce a versioned identity/signature and key-verification abstraction, signed audit checkpoints, key rotation/revocation records and explicit verification failures while preserving unsigned legacy history.
2. **Evidence/dependency integrity:** make recursive dependency manifests first-class, atomically snapshot all declared inputs, validate manifests at plan/review/run/audit/export boundaries, and add protected release-bundle verification.
3. **Provider-neutral dispatch receipts:** define an adapter interface and deterministic request/response receipt schema; implement a local fake adapter first, then add real clients only with provider credentials and captured invocation evidence.
4. **Distributed lease and event boundary:** design a pluggable coordination backend with fencing/lease expiry semantics, then benchmark SQLite history and a bounded archive/compaction path without changing the authority contract prematurely.
5. **Hosted validation:** execute the existing CI matrix, lock/rebuild/export probes and scenario suite on supported OS/Python combinations; record unavailable environments separately.
6. **Research integration:** add source-search adapters, corpus manifests, deduplication and retrieval provenance; keep source access and coverage claims explicit and reviewable.
7. **Scientific and operational hardening:** add real-data/control templates, calibration metadata, statistical review hooks, metrics, retention/recovery drills and signed release publication checks.

Each step should be an additive major task with its own plan, change request, independent three-round debate, result review, versioned evidence and final audit. Phase 2 frozen files and the four historical evidence-loss findings must remain unchanged.

## 7. Baseline conclusion

The existing UADOS implementation is a coherent, tested local governance core. Phase 3 should extend trust, evidence integrity, provider integration, distributed coordination, scale and research retrieval through explicit interfaces and reviewed adapters. Replacing the SQLite/event/projection core would discard validated behavior and is outside this baseline recommendation.
