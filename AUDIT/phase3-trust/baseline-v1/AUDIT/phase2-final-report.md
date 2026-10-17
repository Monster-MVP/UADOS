# UADOS Phase 2 final report

Phase 2 extends the existing dependency-free local UADOS ledger; it does not rebuild its storage or fabricate retrospective governance. Fresh projects use workflow protocol 2. The explicit upgrade retains schema 1, the original event prefix, and protocol-1 interpretation for legacy tasks.

## Architecture

`project.py` owns lifecycle and review gates; `storage.py` owns locking, transactional events, atomic projections and exact-byte evidence archives; `context.py` owns context and Understanding Reports. New `protocol.py`, `orchestration.py` and `governance.py` separate versioning/projections, role/debate control and change/research/improvement records. This keeps provider-independent coordination modular. New adapters specialize file discovery through one maintained master workflow. Extension is possible through declared capabilities, reviewed policies and explicit runtime packets; actual provider dispatch requires an integration. Full-state events favor local traceability but increase storage and verification cost with history.

## Capabilities

Formal startup, task, handover and memory protocols generate and acknowledge Understanding Reports before tracked execution. Every protocol-2 task has an evidence-backed implementation and validation plan. Major work additionally binds seven-field change control, generated role coverage, assignments and three-round analysis/challenge/vote consensus from two eligible independent reviewers. Dissent, rejected alternatives and prior contributors remain visible. Live evidence drift, stale policies and role changes invalidate approval.

Research records preserve truthful literature access and corpus coverage, all seven contribution fields plus coverage limits, provisional independent novelty assessment, a separate falsifiable hypothesis, and exact hypothesis/experiment/run outcomes. Failed execution cannot support a scientific supported/refuted verdict. The scenario reproduces known WLS and records overlap; it makes no scientific novelty claim.

New evidence registration reads bytes once, preserves a verified content-addressed snapshot and records its location. Active gates check both the live source and promised snapshot. Export/Git reconstruction retain archives. Audit reports current consistency separately from historical original-byte availability and fails for a missing or corrupt promised snapshot. Audit findings and investigated fixes appear in the generated improvement log.

## Executed validation

The current suite passed **75 tests** on local macOS arm64/Python 3.9. Independent prior boundary tests and new archive probes inspect ownership, vetoes, selected-role execution, stale research policies, malformed inputs, exact-byte retention, current-path drift, archive corruption and export/rebuild. The three scenarios were rerun under snapshot-aware code in `EXAMPLES/phase2-snapshot-validation`: six application behavior checks, synthetic research with 200 seeded repetitions, and a fresh-process logical Day1/Day30 handover after export/rebuild. The WLS median paired RMSE ratio is 0.7938114563766927 with a conditional bootstrap interval [0.715706307871708, 0.852870340691968].

The rebuilt **1.1.0 wheel includes 48 maintained assets**. Isolated installation, current package-byte equality and a real disposable Git clone reconstruct the root, three historical examples and four Phase2 example projects. `AUDIT/phase2-distribution-v3-final.json`, `AUDIT/phase2-runtime-validation-v3.json`, `AUDIT/phase2-tests-v3.txt` and `AUDIT/phase2-docs-v3.json` retain commands/results. Actual separate model reviewers, distinct from scripted fixture labels, participate in the final plan and result debate; the completed rounds and final state are recorded in `CONSENSUS_DECISION.md` and the final audit, rather than inferred from this report.

## Known limits and integrity findings

Current validation passes, but several earlier Phase2 evidence files were overwritten before archives existed. Historical records remain unchanged and the audit explicitly reports the unavailable original hashes through `history_ok` and `historical_evidence_drift`. These losses cannot be repaired by rehashing replacements; current acceptance uses immutable new revision paths. Phase1 SHA-bound audit/ADR evidence and the original event prefix remain unchanged. Final delivery must be read together with the current audit's historical warnings.

Contributor labels/capabilities cannot authenticate identity or expertise. Adapters supply bootstrap packets; commercial products/providers were not launched. Scripted scenario roles test mechanics, logical dates do not represent 29 elapsed days, and synthetic oracle-weight research does not establish physical validity or publication merit. Hosted Linux/Windows CI, distributed coordination, network-filesystem locks and large-history performance remain unexecuted. Direct editor writes remain outside lease enforcement; the hash chain has no external trust anchor.

## Phase 3

Priorities: authenticated contributor identity and signed audit anchors; provider/native-client dispatch with receipts; protected evidence storage and release artifacts; hosted cross-platform CI; systematic literature access/search integrations; distributed lease coordination; and scalable event storage with performance validation. Domain experiments should add real-data controls, calibration checks and independently reviewed statistical analysis.
