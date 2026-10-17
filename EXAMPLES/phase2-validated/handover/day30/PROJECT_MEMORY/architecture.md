# Project architecture and resource map

This is a maintained document. Replace the prompts with project facts as they become known. Label proposed designs and unverified assumptions; do not fill gaps with invented components.

## Objective and system boundary

- Outcome the project must deliver:
- Intended users or research question:
- Included responsibilities:
- External systems and excluded responsibilities:
- Current phase and next milestone (reference `PROJECT_STATE.md`):

## Components and information flow

| Component or research stage | Responsibility | Inputs and outputs | Owner or task | Failure boundary |
| --- | --- | --- | --- | --- |
| To be established | | | | |

Document interface contracts, data formats and paths. Include a small diagram when it resolves an ambiguity. For a research project, describe the path from acquisition and preprocessing to experiment, analysis and publication; for software, describe request/data flow and persistent state.

## Decisions and constraints

Link applicable ADRs or decision IDs. Record why the current architecture fits the workload, what alternatives were rejected, and which observations would trigger reconsideration.

- Compatibility and environment constraints:
- Data consistency or measurement assumptions:
- Security and privacy boundaries:
- Performance or resource budgets:
- Known limitations and unresolved questions:

## Available resources

| Resource | Version or identifier | Access and availability | Reproduction or replacement |
| --- | --- | --- | --- |
| Runtime / dependencies | | | |
| Compute / instruments | | | |
| Data / external service | | | |

Availability is a current observation, not a permanent guarantee. State who can authorize access and how to detect an unavailable resource. Keep credentials and confidential raw values outside this document.

## Validation and recovery

Reference the project's meaningful validation commands, experiment protocols, backup procedure and recovery limitations. Update this map when boundaries change, and record the rationale through a tracked decision rather than silently replacing the historical explanation.


## UADOS integration map

The common lifecycle is in `MASTER_AGENT_WORKFLOW.md`; `.agent/` contains operational worksheets and client compatibility. `MULTI_AGENT_SYSTEM/` explains generated roles and staged debate/consensus. `CHANGE_REQUESTS/` governs major changes; `RESEARCH_MANAGEMENT/innovation_policy.md` governs literature access, idea/hypothesis records and provisional novelty. Generated registers remain CLI-owned.

Record this project's protocol version, external model/identity integrations if any, actual independent role ownership and unavailable-resource constraints here. Do not infer provider dispatch, hosted CI or native-client validation from the scaffold. Protocol upgrade preserves historical tasks and events; new generated records are evidence inputs only where their operation defines them.
