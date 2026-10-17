# Version control and delivery

Use version control to preserve implementation and maintained documents alongside the UADOS record. UADOS is local and does not create remote repositories, configure protected branches, run hosted CI or deploy software.

## Team workflow

Use a branch or worktree for concurrent implementation where appropriate. Associate changes with task IDs and keep scopes coherent. Inspect existing modifications before beginning; never reset or discard another contributor's work to obtain a clean checkout.

Before requesting review, record the task result and evidence. Review the current scoped contents and attach the relevant artifacts. A commit alone is not a UADOS completion record, and a UADOS approval does not replace remote branch protection.

Make commit messages explain the resulting behavior and its reason. Record significant design rationale as a tracked decision rather than hiding it only in commit text.

## Durable record and backups

Back up the authoritative `.uados/ledger.sqlite3`, maintained context and evidence together. Use a consistent SQLite backup or a quiescent copy; do not copy an actively written database file and assume it represents a complete transaction. Do not merge SQLite binaries by hand. For shared local work, let the CLI serialize mutations through its project lock.

For normal Git commits, version a consistent `.uados/events.jsonl`, `.uados/state.json`, generated/maintained Markdown and needed evidence. Ignore the local ledger, its transient journal files and `.uados/lock`; do not ignore all of `.uados/` if Git is your restoration method. Data/output privacy and size may require an approved artifact store with explicit restoration instructions.

After cloning a revision without the local database:

```sh
python -m uados --project . rebuild-ledger
python -m uados --project . audit
```

`rebuild-ledger` validates exported event sequence, chain and matching state before creating a missing database. It never overwrites an existing one. It cannot establish an export's authenticity. Divergent event chains from parallel Git branches cannot be reconciled by concatenating JSON lines or ordinary text conflict resolution: select a validated coherent history and record how work from the other branch is reconciled.

For a portable initialized directory, use `export PATH` to a new destination outside the source project. Repeated `--include PATH` adds other project-relative files/directories. Verify the destination's audit and the actual workload; installation, external data and unrelated dependencies are not automatically captured.

Generated Markdown and JSON are useful for human review, but are projections rather than alternative sources of truth. If a restore produces projection discrepancies, audit and regenerate from the valid ledger. Retain original artifacts until recovery has been verified.

## Optional CI and release policy

If the team configures CI, make required checks explicit and retain their commands, environment and outcomes as evidence. Avoid credentials in logs. Verify a restored project with `audit` and the relevant software/research checks.

Before release, identify the tested revision, completed tasks, known limitations, migration and rollback procedure. Inspect distributed content for private data and accidental credentials. A public release, remote push or deployment is an external action governed by project authorization, not an automatic result of recording task completion.
