# Initial understanding and bootstrap history

Date: 2026-10-12 (Asia/Shanghai). Source: supplied UADOS v1.0 Part 1 text and direct inspection of the workspace.

Before implementation the workspace was empty, had no Git repository, no prior architecture, and none of the required UADOS context files. The initial understanding was stated before code edits: build a reusable executable project-memory and development framework, starting in design/bootstrap; no previous tasks were complete. Available resources were the local filesystem, Python 3.9.6, standard-library tooling, and independent agent review. Main risks were stale context, conflicting agent edits, split-file durability and completion claims without evidence. Recommended actions were choose the storage/workflow contract, challenge it independently, implement the CLI and templates, then exercise agent switching, recovery and research fixtures.

The primary agent used architecture and codebase-design skills. A separate reviewer challenged the initial design before implementation and later authored adversarial tests without editing the runtime. Another agent produced maintained scaffold documentation. The primary implementer fixed findings and ran the full suite. These are actual collaboration records, not simulated example roles.

UADOS was initialized in its own repository after its bootstrap runtime and scaffold existed. Work before that point cannot honestly be represented as having used gates that did not yet exist. This note preserves that history. Subsequent delivery tasks use the live session/task/review ledger.

Known limits: trusted local coordination, declared scopes, unauthenticated contributor labels and hashes, no distributed identity/deployment service, and research fixtures rather than a scientific discovery claim. Linux and Windows execution remains unverified locally.
