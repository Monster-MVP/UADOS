# Phase 3 provider-neutral dispatch receipt plan (T000009)

## Bounded outcome

Phase 2 generates provider-neutral packets and assigns roles, but no executable adapter boundary records what was sent or returned. Add a small local adapter interface and a deterministic `fake` adapter that accepts a canonical request and emits an immutable receipt. The receipt binds request and response bytes, adapter/provider labels, status and timestamps. This establishes a testable dispatch contract without claiming invocation of Codex, Claude Code, Cursor, Qoder, ZCode or any hosted provider.

## Contract and safety

Requests are project-relative evidence files containing canonical UTF-8 JSON objects with a bounded size and exact `format`, `version`, `provider`, `operation` and `input` fields. `provider=fake` is the only enabled implementation; unknown providers fail explicitly. The fake adapter performs no shell, network or credential lookup and returns a deterministic response digest. An external receipt path is created exclusively, with canonical JSON and a flushed atomic write; existing output is never overwritten. Verification re-reads bounded receipt/request bytes, checks canonical shape, exact request/response SHA-256 and allowed provider/adapter values. Receipts are ordinary evidence paths and can be registered through existing task/research gates.

No private credential, prompt content or arbitrary command is copied into the ledger. No provider invocation is hidden behind a label. Actual provider integrations, credential policy, retry semantics, rate limits, remote receipt custody and distributed idempotency are separate reviewed work. Local timestamps describe execution observation only.

## Validation and recovery

Test real canonical/binary input hashing, deterministic fake response, malformed/duplicate/unknown/noncanonical/bool/oversized requests, unknown provider and output path/symlink/overwrite failures, receipt tampering and request drift. Verify a failed dispatch leaves no receipt and does not mutate the project ledger. Exercise CLI exit codes and ordinary evidence registration, full regression and scaffold. Preserve an explicit prior failure if a probe harness is incorrect. Keep source, receipt and docs versioned; no stable schema/protocol replacement.

## Alternatives

Retain packet-only orchestration (no execution evidence); invoke arbitrary provider CLIs (unbounded command/credential risk); or add a hosted dispatch service (deployment and identity requirements). Choose the local fake adapter plus strict receipt schema as a safe boundary before real integrations.
