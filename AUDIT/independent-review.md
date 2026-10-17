# Independent adversarial review

Date: 2026-10-12 (Asia/Shanghai). Reviewer: `Independent-Design-Reviewer`.

Scope: `src/uados/storage.py`, `context.py`, `project.py`, `research.py`, `cli.py`, and the persisted workflow contracts. The reviewer challenged the proposed architecture before implementation, inspected the runtime independently, and authored `tests/test_adversarial.py`. Runtime fixes were made by the primary implementer. This record describes actual review activity; it does not claim that implementation performed before UADOS bootstrapping was governed by its later CLI gates.

## Verdict

The local, cooperative workflow design is acceptable for v1 delivery after the fixes below. There are no unresolved blocking findings in the reviewed cases. The stated limits remain part of the operating contract, rather than evidence of distributed operation, identity authentication, or complete scientific reproducibility.

## Challenges and verified fixes

| Severity | Failure challenged | Implemented resolution | Verification |
| --- | --- | --- | --- |
| P0 | Separately replacing a state file and event journal cannot create one atomic commit. | SQLite commits the authoritative state and event together; JSON and Markdown are rebuildable projections. | Corrupt state/event disagreement is rejected; journal reconstruction validates the chain before publishing a new database. |
| P1 | A plan reviewer could approve a major task, then claim the same implementation using their own approval. | Claim evaluates approval with the prospective implementer excluded. | A reviewer cannot claim without a separate eligible plan approval. |
| P1 | An expired lease could transfer implementation to the accepted plan reviewer, bypassing the initial-claim check. | Accepted plan reviewer identities remain recorded and cannot take over that implementation. | Expired takeover is rejected without changing the previous owner. |
| P1 | After handover, a previous implementer could review their own inherited result because only the newest implementer was excluded. | All historical implementation contributors remain excluded from reviews and approval counting. | A separate author, original implementer, successor implementer, and returning contributor reproduce the bypass; the corrected runtime rejects it. |
| P1 | Root implementation scope included generated records; recording a review changed its own approval fingerprint. | Generated projections and session reports are omitted from implementation snapshots. | `--scope .` permits a reviewed claim without self-invalidating its approval. |
| P1 | Scientific analysis evidence was omitted from audit and export. | Run interpretation evidence is checked and transferred alongside output artifacts. | Export contains the analysis; subsequent analysis modification makes audit fail. |
| P1 | Non-UTF-8 generated exports prevented their own repair. | Projection drift detection treats corrupt generated content as rebuildable drift. | `audit --repair` restores corrupt state JSON from the database. |
| P2 | Valid JSON of the wrong shape caused an uncaught exception during integrity checking. | Ledger structure errors produce workflow errors. | Array-shaped state and null-shaped event records are rejected cleanly. |

## Executed validation

Executed locally on Darwin arm64 with Python 3.9.6:

```sh
python3 -m unittest discover -s tests -p 'test_adversarial.py' -v
```

Result: **29 tests passed**, 2.634 seconds. The final run includes the historical-contributor regression added after the initial 28-test run. No Linux, Windows, or hosted CI execution is claimed here.

The suite exercises unacknowledged and stale contexts, maintained-rule changes, forged report hashes, concurrent process sessions and task claims, scoped code and review evidence changes, reviewer independence across handover, corrupt ledger/export refusal, reconstruction with missing state JSON, traversal/symlink rejection, generated-directory write boundaries, timed-out and unavailable commands, durable launcher crash intent, successor recovery, analysis evidence transfer, and successful commands whose changed code invalidates their provenance.

Crash injection raises an unexpected exception at subprocess launch after experiment intent is persisted. It verifies recoverable running state and explicit successor resolution; it does not simulate electrical power loss. Concurrent tests execute distinct processes against one local project.

## Remaining limits

- CLI gates coordinate cooperative agents. Agents can still edit files outside the CLI; recorded scope is not an operating-system sandbox.
- Different reviewer labels and contributor exclusion support traceability. They cannot authenticate a human or prove that separate model processes were independently controlled.
- The hash chain checks local consistency. A party controlling all records can rewrite and rehash history without an external trusted anchor.
- SQLite locking coordinates a local shared checkout. Network filesystems, distributed replicas, and cross-machine lease consensus were not validated.
- Experiments retain command arguments, environment metadata, configuration/data fingerprints, output evidence, and declared code scope. They do not automatically apply the seed, capture every external dependency, preserve unavailable datasets, or establish scientific validity.
- Scope and provenance quality depend on accurately declaring relevant files. Command runtime metadata for alternate interpreters or containers must be supplied by the command itself.

These limits should remain visible in contributor onboarding and release documentation. Additional platform claims require execution on those platforms; production identity or tamper guarantees require separate infrastructure.
