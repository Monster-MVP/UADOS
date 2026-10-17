# Audit and recovery

The ledger is authoritative; generated files are readable projections. Audit checks consistency of the stored record and recorded evidence. It cannot establish that a scientific claim is correct or that a collaborator is authentic.

```sh
python -m uados --project . audit
python -m uados --project . audit --repair
```

Use the command's result and diagnostics as the record of what was inspected. `--repair` regenerates projections from a valid ledger. It does not rewrite history, invent missing evidence or restore altered scoped files.

## Recovery decisions

| Observation | Interpretation | Response |
| --- | --- | --- |
| Generated Markdown or JSON differs | Projection drift or interrupted generation | Preserve useful diagnostics, then repair projections and audit again |
| Evidence is missing or changed | The recorded claim cannot be verified against its original artifact | Restore the exact artifact from a trusted backup or rerun validation and record new evidence; obtain a fresh review when needed |
| Ledger hash chain or state is inconsistent | Authoritative-record integrity is uncertain | Stop tracked work, preserve a copy and restore a verified backup; do not “fix” the chain by hand |
| Session context is stale | Recorded state or maintained context changed | Refresh, inspect the new report and acknowledge its hash |
| Conflicting active ownership | Parallel work overlaps or an earlier owner left | Coordinate takeover and record the reason; do not remove a lock or overwrite files blindly |
| Experiment was interrupted | Execution may have partial outputs or a surviving process | Inspect execution state, stop it through an appropriate authorized mechanism if needed, then use `experiment resolve` with the recovery reason before a safe rerun |
| Required resource is unavailable | Validation cannot establish the intended claim | Record a blocker and recovery action; do not call the result empty or passing |

## Locking and interrupted writes

The CLI holds a stable operating-system project lock across record mutation and projection generation. Process exit releases the operating-system lock; the lock file may remain and is not itself evidence that a process still owns it. Do not unlink a lock file to bypass a competing writer, because separate writers could then lock different inodes.

SQLite commits ledger event and current state together. Projection files are generated after that commit and can be rebuilt if generation stops. An interrupted projection write therefore needs regeneration, while a failed database commit needs investigation of the record before further work. If the CLI reports that an event committed but projection generation failed, do not repeat the original action: repair and inspect the committed state first.

## Preservation and restart

Keep a verified backup of ledger, maintained documents and relevant evidence. Before destructive recovery, retain the original files and diagnostics. After restoring, audit, inspect the latest handover and start a new acknowledged session. Revalidate external resources; a copied project does not establish their current availability.

If the local database is absent after a Git clone, `rebuild-ledger` can reconstruct it from a complete validated `.uados/events.jsonl` and matching exported state when present. Preserve a consistent Git revision of memory and evidence as well. The command refuses an existing database; it is not a corruption-overwrite mechanism. If exports disagree, recover a coherent revision instead of editing hashes until validation passes.

When an audit reveals a repeated failure, record a lesson and review a bounded policy improvement using `ENGINEERING_RULES/extensions.md`.
