# Research innovation and novelty policy

Lifecycle authority: [MASTER_AGENT_WORKFLOW.md](../MASTER_AGENT_WORKFLOW.md). Innovation is a falsifiable research proposition grounded in known work and access limits. An audit simulates critical peer review; it cannot certify universal novelty or guarantee publication.

## Literature and access

Register each source with a stable source identifier, primary HTTP(S) location, relevance, limitations, observed access level, corpus group and supporting evidence. Registration does not fetch the URL. Use `full_text`, `abstract` or `unavailable` truthfully. Two records of the same source do not count as two independent prior works. Record retrieval/search scope, dates, queries, exclusions and unresolved access in coverage evidence. A failed search source is unavailable, not an empty literature result.

Keep copyrighted/restricted material within authorized access. Store manifests and permissible summaries when raw sources cannot be distributed. A local hash proves byte consistency, not that the source says what the summary claims.

## Idea and hypothesis

Every idea contains these seven fields:

| Field | Review question |
| --- | --- |
| Existing Work | Which specific prior studies are the strongest baseline? |
| Current Limitation | What observed limitation remains under which conditions? |
| Scientific Gap | Which unresolved scientific question follows from that evidence? |
| Proposed Innovation | What mechanism or method changes, and how can it be tested? |
| Why Previous Methods Cannot Solve It | Which assumption or demonstrated boundary defeats the alternatives? |
| Expected Contribution | What measurable knowledge/result would the study add? |
| Publication Potential | Which audience could benefit, with what uncertainty and required evidence? |

Register falsifiable hypotheses separately and link them to the idea. A hypothesis specifies a prediction, an observation that would reject it and a testing method. Broad aspirations and a successful process exit are not hypotheses. Protocol-2 experiments link both idea and hypothesis IDs while preserving command, input/config/data/code/environment evidence.

## Independent novelty audit

An eligible independent reviewer inspects the idea, source contents, access limitations and search coverage. Record a reasoned verdict:

- `candidate`: provisionally plausible contribution within recorded coverage; requires at least two distinct full-text sources from distinct corpus groups and coverage evidence. Every supporting source linked to a candidate idea must have full-text access; abstract-only/unavailable support cannot be silently counted.
- `overlap`: prior work materially overlaps; identify it and explain whether a narrower claim remains testable.
- `inconclusive`: evidence, access or coverage is insufficient; name what could resolve the uncertainty.

Source/idea/policy/evidence changes can make an audit stale. Renew the audit rather than presenting old evidence as current. Record hypothesis tests and interpretation separately; process failures, invalid runs, valid negative findings and inconclusive scientific results must remain distinguishable.

Generated `LITERATURE_GAP_ANALYSIS.md`, `NOVELTY_AUDIT.md`, `RESEARCH_DECISION_RECORD.md` and `HYPOTHESES.md` are ledger projections. Use research operations to update them. Candidate novelty remains provisional even after a clean local audit; external peer review, broad literature coverage and domain-valid experiments are future evidence, not implied by these records.


## Structured input shapes

These are schema examples, not retrieved sources or scientific findings. Replace placeholders, verify access and create readable evidence before using `research source --record evidence/source.json --session SESSION_ID`, `research idea --record evidence/idea.json --session SESSION_ID` and `research hypothesis --record evidence/hypothesis.json --session SESSION_ID`. Use issued source/idea/hypothesis IDs.

```json
{
  "title": "Source title",
  "identifier": "Stable primary source identifier",
  "url": "https://example.org/replace-with-primary-source",
  "claim": "Permissible evidence-backed summary",
  "limitation": "Limit of access or method",
  "access": "unavailable",
  "corpus": "Distinct primary work or corpus group",
  "evidence": ["evidence/source-access.md"]
}
```

The default unavailable value illustrates honest access recording; it cannot support candidate novelty. Use `full_text` only after actual access. Two sections/URLs from one handbook or corpus are not distinct corpus coverage.

```json
{
  "title": "Testable proposed contribution",
  "fields": {
    "existing_work": "Specific strongest prior work",
    "current_limitation": "Observed boundary and conditions",
    "scientific_gap": "Unresolved question grounded in evidence",
    "proposed_innovation": "Testable proposed mechanism",
    "prior_methods_insufficient": "Evidence-backed reason alternatives fail",
    "expected_contribution": "Measurable new result or knowledge",
    "publication_potential": "Audience, uncertainty and required evidence",
    "coverage_limit": "Search/retrieval scope and missing work"
  },
  "sources": ["SOURCE_ID_1", "SOURCE_ID_2"],
  "evidence": ["evidence/coverage-and-analysis.md"]
}
```

`coverage_limit` is an additional mandatory scope disclosure alongside the seven innovation fields.

```json
{
  "idea": "IDEA_ID",
  "prediction": "Falsifiable expected effect under stated conditions",
  "baseline": "Comparator and controls",
  "metric": "Measurement, units and experimental unit",
  "rejection": "Observation or threshold that rejects the prediction",
  "uncertainty": "Replication, variability and known confounds",
  "evidence": ["evidence/experimental-design.md"]
}
```

Use `experiment add ... --hypothesis-id HYPOTHESIS_ID` with its complete command/config/dataset/seed/scope packet. After inspecting a resolved run and refreshing context, use `research outcome HYPOTHESIS_ID --experiment EXPERIMENT_ID --run RUN_ID --verdict supported|refuted|inconclusive --reason ... --evidence ... --session SESSION_ID`. Choose one verdict value. Failed/interrupted/invalidated execution can support only an inconclusive operational outcome, not a scientific supported/refuted finding. `experiment conclude` preserves the detailed scientific interpretation separately.
