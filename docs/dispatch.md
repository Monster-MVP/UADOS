# Provider-neutral dispatch receipts

`dispatch run` accepts a project-relative canonical request JSON and writes a new external receipt. The only enabled provider is `fake`; it performs deterministic local work without shell, network or credential access. The request contains exactly `format`, `version`, `provider`, `operation` and `input`. The bounded receipt binds the exact request hash, fake adapter identity, operation, deterministic response hash and success status.

```sh
python3 scripts/uados.py --project . dispatch run \
  --request requests/example.json --output /secure/uados/receipt-001.json
python3 scripts/uados.py --project . dispatch verify \
  --request requests/example.json --receipt /secure/uados/receipt-001.json
```

Output files are external, new and exclusive. Existing paths, symlinks, traversal, project-internal paths and malformed requests fail before a receipt is published. Verification re-reads bounded canonical bytes and rejects request drift, receipt tampering, provider or adapter mismatches and non-deterministic responses. Dispatch and verification do not append UADOS ledger events. To make a receipt ordinary project evidence, copy it into an approved project-relative path through the normal evidence workflow and inspect disclosure before sharing.

Both creation and verification reject symlinks in the complete external path;
use the resolved path when the operating system exposes a temporary-directory
alias. Receipt timestamps require ISO8601 timezone offsets and an end observation
at or after the start. They remain unauthenticated local clock observations.
Receipt verification checks deterministic request/response consistency, not
cryptographic authenticity of the receipt; preserve its digest or register its
bytes under the reviewed evidence and signed-checkpoint workflows when needed.

The fake receipt proves local adapter mechanics only. It does not prove a real provider invocation, model identity, network delivery, credentials, retry behavior, organizational authorization, prompt completeness or scientific quality. Real provider adapters require separate reviewed contracts for credentials, rate limits, remote receipt custody and idempotency.
