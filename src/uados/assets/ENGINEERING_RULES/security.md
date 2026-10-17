# Security and trust boundaries

## Local trust model

UADOS is a local coordination and provenance tool for trusted collaborators. Anyone with write access to the project can modify implementation, evidence and the SQLite ledger. A hash chain detects accidental inconsistency and unsynchronized edits under the tool's model; it is not a signature, an authenticated audit service or a defense against a writer who rewrites the record.

Agent IDs are team-chosen labels. Distinct IDs support ownership and review checks, but cannot prove a distinct person or model performed the review. Use organizational identity, protected storage or external review systems if stronger guarantees are required.

Task scope and leases coordinate work; they do not restrict editor or operating-system access. Tracked-command acknowledgement cannot prove a contributor read the report. Hold contributors responsible for these policies.

## Secrets and sensitive data

Never commit tokens, passwords, private keys or access credentials to notes, evidence, commands, configuration snapshots or handovers. Use the project's approved credential mechanism. Record only the name of the required secret and how an authorized contributor obtains it.

Minimize sensitive data in logs and manifests. Record access restrictions and de-identification needs. A reproducibility goal does not authorize sharing personal, proprietary or restricted data. Inspect an export or release for accidental disclosure before sharing it.

## Executable inputs

Treat code, downloaded files, dataset processing scripts and command arguments as executable trust decisions. `experiment run` executes the recorded argument vector with the user's privileges. It is not a sandbox. Read the command and relevant program before execution; bound runtime and resources where feasible. Avoid destructive commands or shell wrappers unless explicitly necessary and authorized.

Fingerprinting a file does not make its contents safe. Validate format and size assumptions at ingestion, and record source and license before incorporating external material.

## Review triggers and response

Use major review for authentication, authorization, exposed interfaces, handling of sensitive data and persistent-record integrity. Examine concrete failure paths, least privilege, input validation, dependency provenance and recovery.

When a security issue is found, preserve a minimal sanitized reproducer, document impact and uncertainty, assign ownership and avoid distributing exploit details beyond the authorized audience. If credentials were exposed, use the organization's rotation process; editing the visible file does not remove all historical copies.
