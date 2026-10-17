# Independent challenge prompt

Review task `<TASK_ID>` at stage `<plan or result>` independently from its author and implementer. Your goal is to identify a concrete way the proposal could fail or its conclusion could be unsupported.

Start an independent session with your stable contributor label, inspect current context and acknowledge the report hash. Read the relevant plan or result, scoped files, evidence, acceptance criteria and governing rules. Do not accept the implementer's summary as sufficient proof.

Choose the strongest plausible challenge: a hidden assumption, boundary/failure case, security or data-integrity issue, incompatible interface, unfair baseline, leakage, confounding or alternative explanation. Investigate it with relevant evidence or a check. Identify findings that could materially change the decision and distinguish observations from uncertainty.

Write a review artifact using `TEMPLATES/review.md`. State what was inspected and what was unavailable; never claim to have run an unexecuted check. Give `approve` or `request_changes` with a concrete reason and challenge. Record it using `task review TASK_ID --stage ... --verdict ... --challenge ... --evidence ... --session ...`.

Use a label distinct from the task's author and implementer. Real independence is a team obligation; choosing a different string does not establish it. A result approval applies to current task, scoped files and evidence, and must be renewed after consequential edits.
