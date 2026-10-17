# Project memory

Memory belongs to the project, independent of a contributor's model, chat or machine. A new contributor should be able to reconstruct what was attempted, what worked, what failed and why the next step follows.

## What goes where

| Knowledge | Record |
| --- | --- |
| Objective, mode, phase and work state | Generated `PROJECT_STATE.md` |
| Architecture, boundaries and resource assumptions | Maintained `architecture.md` |
| Structured tasks, dependencies and ownership | Generated `tasks.md`, edited through CLI commands |
| Significant choices and alternatives | `decision add`, projected into `DECISION_RECORD.md` |
| Technical explanations, lessons and failures | `note` projected into `knowledge.md`, or maintained `notes/*.md` |
| Experiments and execution records | `RESEARCH_MANAGEMENT/experiments.md` through the experiment commands |
| Session stopping point | `session close`, projected into `SESSION_HANDOVER.md` |
| Detailed proof of a claim | An evidence artifact linked to its task, decision or review |

Create `notes/` when needed. Name notes by subject or stable identifier. A durable note should include its source, date or event, scope, conclusion, uncertainty and the next decision it affects. Link to local evidence and relevant task or experiment IDs. Avoid duplicating mutable task status in several documents.

## Memory quality

Describe evidence strength explicitly: observed, inferred, proposed or unverified. Preserve rejected alternatives and the condition under which they might become useful. An error without its command and inputs is rarely a useful failure record.

Prefer relative paths inside the project so memory survives copying. For external or restricted resources, store a manifest containing a stable identifier, version, checksum if available, access conditions and retrieval instructions. Do not pretend those resources were included in a project export.

No conversation should be the sole record of a consequential decision. Capture such knowledge before closing the session. Maintained notes are context inputs; edit them deliberately, and refresh an affected session before further tracked work.

`knowledge.md` and `session_reports/` are generated from the ledger. Preserve them through the recorded note/session lifecycle rather than hand-editing their contents.
