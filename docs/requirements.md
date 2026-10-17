# Requirements and acceptance model

This implementation follows the supplied UADOS v1.0 Part 1 request and its Phase 2 extension. The operating framework combines local executable gates with maintained human/agent policies. The table distinguishes mechanisms from responsibilities that cannot be established by a local CLI alone.

| Requirement | Implemented mechanism | Acceptance evidence or review |
| --- | --- | --- |
| Context before action | Issued Understanding Report, exact hash acknowledgement and current context checks before tracked work | Unacknowledged, incorrect-hash and changed-policy operations are rejected; refresh permits an informed restart |
| Agent-independent project memory | Project-local SQLite ledger, Markdown/JSON views, decisions, notes and handovers | A second session recovers objective, decisions, failures, blockers and next actions without earlier chat |
| Documentation as development | Explained task result, evidence requirement, maintained architecture and research/policy templates | Completion without a work submission/evidence is rejected; reviewers assess explanatory adequacy |
| Reasoned important decisions | Structured ADR fields with at least two alternatives, reason, evidence and risk; major-task linkage | Decision records preserve rationale and significant linked decisions await reviewed task completion |
| Adversarial multi-agent review | Distinct contributor labels, challenged plan/result records, fingerprints and scope ownership | Major claim/completion without relevant independent approval is rejected; team verifies real independence |
| Software/research/hybrid modes | Evidence-based initialization heuristic and explicit override, common lifecycle plus research execution | Software/research evidence selects the expected mode; empty projects default to software with low confidence |
| Reproducible research | Registered argument vector, config/data/code fingerprints, seed metadata, launcher provenance, outputs and separate interpretation | Recorded execution and analysis can be inspected; researchers supply missing environment/data/design information |
| Extensible workflow | Maintained rules, extension template, rationale and context invalidation for governed policy edits | A policy change makes an existing session stale; new automation is separately implemented and validated |
| Long-term portability | Consistent local export and validated missing-ledger reconstruction from exported event history | The copied/reconstructed project passes audit and preserves task/decision/note history |
| Integrity and recovery | One authoritative ACID ledger, hash chain, stable lock, atomic view writes, audit and limited projection repair | Projection failure remains repairable without repeating committed work; altered evidence is not “repaired” by rewriting views |
| Required project structure | Packaged maintained assets and generated state views | Initialization creates every required directory and readable entry point without overwriting existing project files |

## Required project components

Initialization provides `README.md`, `MASTER_AGENT_WORKFLOW.md`, `PROJECT_MEMORY/`, `ENGINEERING_RULES/`, `MULTI_AGENT_SYSTEM/`, `RESEARCH_MANAGEMENT/`, `VERSION_CONTROL/`, `AUDIT/`, `TEMPLATES/`, `PROMPTS/` and `EXAMPLES/`. It additionally provides `AGENTS.md` and generated state/history/decision/handover records. Scaffold templates describe what to fill with project facts; generated registers start honestly empty.

Without `--adopt`, an existing target containing colliding scaffold files is rejected rather than overwritten. `init --adopt` preserves existing maintained files such as README, AGENTS and architecture documents, reports `preserved_files`, and fills missing maintained components. Contributors must inspect and integrate preserved onboarding instructions. Collisions with generated views still fail; adoption never silently replaces a previous generated state or a maintained instruction.

## Acceptance scenarios

1. **New project:** Install the package, initialize a clean target, inspect mode-detection evidence, start a session, read its report and acknowledge the exact hash.
2. **Routine task:** Define acceptance criteria, scope and dependencies; claim, implement, run meaningful validation, record evidence and complete. An unsatisfied dependency, conflicting active declared scope or missing evidence prevents the relevant action.
3. **Major task:** Record a plan; use an actually independent contributor for a challenged plan review; refresh implementer context and claim; submit results; review their current contents independently; refresh and complete. Self-review or stale scoped evidence is rejected.
4. **Agent switch:** Record a failure, reasoned decision and next action, close the session, then start another contributor's session. The replacement report and project files preserve the needed context.
5. **Research run:** Register an explicit hypothesis and input/code packet, run it with a timeout, inspect captured output, refresh and record an evidence-backed interpretation with uncertainty. Exit success alone is not a scientific result.
6. **Interrupted generation:** Simulate a projection failure after a commit. Audit finds projection drift; repair rebuilds from the ledger and the event remains recorded exactly once.
7. **Portability:** Export to a new external directory; audit and inspect it. Separately remove the local database only in a disposable copy and reconstruct from validated events to model a Git clone.
8. **Policy extension:** Edit a governed policy, observe stale-context rejection, then inspect and acknowledge the refreshed report. Verify any claimed new automated check separately.

Automated coverage lives in `tests/test_workflows.py`; the project's final verification report records which checks were actually executed. Maintained policies also require substantive reviewer judgment: tests cannot prove honesty, comprehension, novelty or independent identity.

Source-repository executable walkthroughs are in `scripts/run_examples.py`, covering software, research and hybrid operation. `scripts/verify_scaffold.py` checks scaffold completeness. Their scripted agent labels exercise CLI identity gates; they are not proof that the example's reviewer was a separate person or model.

## Operational scope

The v1 runtime uses Python's standard library and local storage. There are no provider/API keys, background services or network features. Git revision capture is optional and does not make Git a runtime dependency for ordinary project work.

The framework provides architecture, quality, security, data, literature, publication and release guidance. It does not automatically set up hosted CI/CD, cloud accounts, identity systems, protected branches, statistical analysis, instruments or a literature-search service. Those capabilities are extension/integration responsibilities with explicit project authorization and verification.

The local ledger cannot prevent direct file edits, establish a contributor's identity, prove an acknowledgement represents reading, resist a malicious writer who rewrites all hashes, or guarantee preservation without backups. These are explicit trust-boundary limitations, not claims hidden behind the term “enterprise.”


## Phase 2 requirements and acceptance

| Requirement | Executable mechanism | Evidence needed |
| --- | --- | --- |
| Formal agent runtime | Stable sessions, issued Understanding Report, exact acknowledgement and evidence-backed task plan | Unacknowledged/stale work and missing protocol-2 plans rejected; startup packet preserved |
| Additive migration | Explicit protocol-2 enablement, schema1 ledger retained, per-task protocol interpretation | Baseline event hashes and Phase1 evidence unchanged; legacy tasks remain completable under their gates |
| Dynamic role generation | Task/mode-based coverage and registered declared capability selection | Software/research role variants, uncovered capabilities and assignment ownership exercised |
| Real adversarial process | Ordered analysis/challenge/vote/consensus, fixed participants, at least two independent reviewers | Missing rounds, self-review, unsupported selection, dissent and stale input paths rejected; substantive independent review supplied separately |
| Enterprise change control | Task-linked seven-field requests, two alternatives and readable evidence | Claim rejected without required major records and approvals; generated CR record agrees with ledger |
| Innovation audit | Source IDs/access, seven-field ideas, falsifiable hypotheses and independent provisional verdicts | Unavailable/abstract-only/duplicate-source coverage cannot support candidate; overlap/inconclusive retained |
| Reproducible experiment links | Idea/hypothesis associations plus existing command/input/environment provenance | Linked run, interpretation and recovery distinguish operational failure from scientific negative findings |
| Shared client authority | Thin AGENTS/CLAUDE and Cursor `.mdc` entry files with explicit master reading | Hidden/nested assets included in installed wheel; references consistent; native product execution claims require separate evidence |
| Self-improvement | Audit stays read-only by default; explicit deduplicated proposed improvement records | Repeat finding does not create uncontrolled duplicates or execute fixes; unknown cause remains explicit |
| Long-term recovery | Rich handover/context and preserved ledger contributor history | Incoming identity reconstructs status, decisions and unfinished work without previous chat |

Additional initialized components include `.agent/`, `CHANGE_REQUESTS/`, `CLAUDE.md`, `.cursor/rules/uados.md` and the actual loader wrapper `.cursor/rules/uados.mdc`. Role, consensus, change, improvement, literature-gap, novelty, research-decision and hypothesis views are generated from ledger state rather than copied as maintained fixtures.

The Phase 2 scenario runner must execute a new software project with startup/planning/review/memory updates, a research project with literature/hypothesis/experiment/novelty records, and an outgoing/incoming agent handover under logical Day 1/Day 30 labels. These are real local CLI/state exercises with simulated commercial-client identities; report exact commands, assertions and failures. Model dispatch is manual and the scenarios cannot authenticate model identity or prove 30 elapsed days.

Preserve `AUDIT/scenario_test_report.md`, `AUDIT/phase2-final-report.md` and `AUDIT/self_review.md` as new evidence. Final assessment covers modularity/extensibility/maintenance, startup/context/role capability, documentation/testing/consistency, reproducibility and innovation analysis. Self-review asks whether new contributors can recover context, collaborate and trace decisions, what actually executes, and what weaknesses remain. Packaging tests must exercise an isolated installed wheel including hidden rules; Git reconstruction must retain current registry/evidence records.

Platform/product claims remain bounded to executed evidence. Local checks cannot prove honesty, native-client obedience, capability competence, actual contributor independence, global novelty, instrumentation validity or distributed reliability.
