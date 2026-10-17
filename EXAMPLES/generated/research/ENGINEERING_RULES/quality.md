# Quality and evidence policy

## Risk classification

Use `routine` for bounded changes with well-understood failure modes. Use `major` for architectural changes, public compatibility changes, security or privacy boundaries, persistent-state integrity, costly experiments, consequential scientific claims or other decisions with substantial impact. When uncertain, describe the uncertainty and select review depth proportionate to potential harm.

Major tasks require independent plan approval before claim and independent result approval before completion. The reviewer must be a different contributor in practice as well as have a different recorded agent label. A change in scope, evidence or result can invalidate the relevance of an earlier review.

## Evidence requirements

Evidence should answer the claim. A passing command is insufficient when it tests the wrong property. Record:

- The relevant acceptance criterion or hypothesis.
- Exact commands or procedures, inputs and environment.
- Exit status and material output, including failures.
- Expected and observed behavior, uncertainty and uncovered limitations.
- A durable artifact path and the task, decision or experiment it supports.

Use targeted regression checks for behavior changes, boundary and failure checks for integrity-sensitive code, and suitable experimental analysis for research. Routine documentation edits usually need link/consistency review rather than artificial unit tests. Follow additional checks required by the project's toolchain.

Evidence fingerprints reveal a difference from recorded bytes. They cannot establish that an output was honestly produced or that a conclusion follows from it. Review the substance.

## Definition of done

A task is ready to complete when the intended behavior exists, the acceptance criteria are assessed, meaningful validation evidence is recorded, relevant documentation and decisions are updated, and material limitations have owners or explicit disposition. Major work additionally needs an approved result covering the current task, scoped files and evidence.

Do not mark a task complete merely because the implementation compiles, an experiment exits successfully, or a chat message asserts success. If criteria remain unmet, record a blocker or follow-up with a concrete next action.

## Defects and lessons

For a defect, preserve a reproducible trigger and observed impact. Record the failed assumption, fix and verification. Generalize a repeated issue into a reviewed policy extension only when the new rule has a clear benefit and bounded cost. Keep the original evidence so the rule can later be evaluated.
