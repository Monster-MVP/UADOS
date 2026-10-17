# ADR 0002: additive workflow governance

Date: 2026-10-12. Disposition is tracked by the Phase 2 tasks and independent reviews in the ledger; this maintained document records design rationale rather than duplicating mutable task status.

## Problem and background

Phase 1 supplies working local transactional memory, acknowledged context, independent review and experiments. Static review and prose-only orchestration do not adequately record role coverage, multiple independent challenges, enterprise changes or the evidence limits of innovation claims. Phase 2 must add executable governance without erasing successful historical tasks, SHA-bound evidence or recoverable ledger events.

## Alternatives

1. Add only documents and prompts. This improves guidance but cannot validate planning, quorum, round order or evidence staleness.
2. Replace persistence and rewrite old tasks into a new schema. This creates unnecessary migration/integrity risk and falsely implies historical compliance with later rules.
3. Introduce hosted provider orchestration, authentication and distributed consensus immediately. This exceeds available identity/provider infrastructure, adds cost/authority assumptions and obscures the current cooperative local boundary.
4. Extend the existing transaction interface with explicitly versioned governance records. This retains a tested durability boundary and makes new gate/evidence behavior independently testable.

## Decision

Choose the additive design. Keep SQLite schema1 and full-state hash-chained events. Fresh projects use workflow protocol2; existing projects record an explicit upgrade through owned reviewed work. Every task keeps its applicable protocol. New modules separate protocol/plan gates, role/debate orchestration and change/research/improvement governance while using the existing Project transaction, storage and projection mechanisms.

Protocol2 adds evidence-backed plans; major work adds a seven-field change request, two alternatives, role coverage and staged plan/result consensus plus independent approval. At least two independent reviewers participate. Registry capability labels are declarations; ownership/conflict history is retained. Consensus binds source/policy/task/assignment/capability/evidence, selects an actual analysis and preserves challenges/votes/dissent.

Research adds identified sources with honest access and coverage, seven-field ideas, distinct falsifiable hypotheses linked to experiments, and independent provisional novelty verdicts. Candidate claims require at least two distinct full-text sources and coverage evidence. Normal audit remains read-only; explicit improvement recording deduplicates proposed work without applying fixes or inventing root causes.

Use one master lifecycle with thin native product entries and subordinate `.agent/` worksheets. Package hidden/nested assets. A provider-neutral dispatch packet creates an integration boundary; actual independent provider dispatch remains a host/team responsibility.

## Impact and risks

Additional records increase state/event size and review effort. Deterministic roles may miss domain coverage. Frozen fingerprints can require renewed debate after meaningful changes; carefully exclude generated/self-referential inputs. Preserve old approval interpretation and old evidence bytes even when current scope changes produce historical warnings.

Local identities and capabilities are not authenticated. CLI gates cannot prevent direct edits, prove independence/comprehension or certify global novelty. There is no OS sandbox, external hash anchor, distributed consensus or automatically executed provider/service integration. Logical-day handover scenarios do not establish elapsed days or actual commercial-client use.

## Validation and recovery

Acceptance needs legacy regressions, new gate/round/staleness/access/migration checks, three executed software/research/switch scenarios, isolated wheel asset verification and Git reconstruction. Preserve immutable Phase1 event/evidence hashes and new failed attempts. Assess independent substantive challenges separately from scripted label-based controls.

Keep current project protocol/task state recoverable through the existing export/rebuild path. Projection repair regenerates views from valid authority and cannot fix corrupt ledger/evidence. Treat incomplete upgrade or changed input issues as recorded recovery work, not permission to rewrite historical events. See new Phase2 AUDIT evidence for executed results; this decision document does not claim unexecuted checks passed.

Revisit when actual provider dispatch, authenticated identities, distributed operation, large-history performance or deeper domain evidence is required. Split new integrations into reviewed ownership and validation scopes.
