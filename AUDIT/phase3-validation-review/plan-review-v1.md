# Independent Phase 3 testing plan review

Reviewer: Phase3-Validation-Reviewer / S000012, a separately dispatched model worker; no implementation or test-suite authorship. Date: 2026-10-13 Asia/Shanghai. Task: T000007. Plan bytes SHA256 14517f91d4f3db5533652a8477195c38eb7b37430c5c1d16ac07f0fb470ef69f.

Inspected MASTER_AGENT_WORKFLOW, .agent startup/task/memory/handover/compatibility, maintained architecture, project task/dependency records, engineering software/quality/security/extension policies, debate/review/selection/consensus and change policies, baseline, plan-v1 and change-v1, storage.py and Project.read/audit/mutate. Trust implementation/test/docs were absent at this plan review; no result validation is claimed.

## Proposed approach and alternatives

Approve a bounded optional SSHSIG checkpoint boundary using explicit external private key and allowed-signers policy, fixed namespace, mandatory externally trusted digest pin and explicit expected principal. Preserve schema1/protocol2 and unsigned events. Sign an exact lock-consistent snapshot; do not append an event. Verify real cryptography before payload use, then match immutable project first-event identity, sequence/head and canonical state to a fully validated chain. Return current audit separately; a prefix is not current approval. Keep richer identity/provider/distributed integration as separate reviewed work. Pure-Python cryptography introduces unjustified crypto maintenance risk; a managed identity service may become preferable when organizational enrollment/rotation/availability requirements and authorized infrastructure exist.

## Concrete testing challenges

1. A self-rehashed attacker ledger can still pass local audit: a valid detached signature must fail against a different head/state/project, and current verification must reject an older sequence. A trusted expected digest must reject substituting a different legitimate signed checkpoint. Test wrong principal/key/namespace and both textual/key-revocation policy using real cryptography.
2. Current audit at verification cannot reproduce a checkpoint-time audit from past live files. Signed audit data is a historical signer assertion; return and label current audit independently. Do not imply retrospective evidence-byte validation merely by reconstructing old event state. Verify changed live evidence fails current audit and preserve four prior original-byte losses.
3. Output immutable publication must have an exclusive creation boundary. Two concurrent outputs to one target must not overwrite an existing bundle, leave a partial visible success or follow a symlink. Failure before successful signing must clean staging artifacts and preserve ledger bytes/event count. Project lock prevents CLI interleaving only, not arbitrary editors or malicious external-policy writers.
4. Canonical payload parser should reject duplicate JSON keys, ambiguous unknown fields, booleans where integers expected, non-finite numbers, overlong/oversized input, missing signature, symlink/alias inputs and inside-project key/policy/output. Bound subprocess and lock impact; test absent executable, malformed signature, process errors/timeouts explicitly.
5. Existing 75 tests and scaffold stay meaningful regression checks. New trust tests must actually execute ssh-keygen; mocked subprocess-only success is insufficient. Keys remain outside project/evidence, ephemeral test directories are removed, and logs contain no private material. New validation outputs need unique immutable paths and exact source revision hashes.

## Executed host capability evidence

AUDIT/phase3-validation-review/plan-ssh-capability-v1.json records seven real OpenSSH_10.3p1/LibreSSL_3.3.6 checks: Ed25519 signature creation and valid verification succeeded; wrong principal, wrong public key, wrong namespace, tampered message and revoked public key all rejected. Temporary keys were external to the project and deleted after the probe. This validates the local optional boundary capability, not UADOS implementation behavior or hosted platforms.

## Plan disposition

The written plan covers the bounded acceptance criteria and preserves production gaps honestly. Plan approval is supportable provided result checks demonstrate failure-closed signature/pin/ledger/path/runtime/output semantics and distinguish historical audit assertions from current audit. No release/deployment/provider/organizational-identity claim is approved. Implementation may reveal a blocking defect requiring changes; this plan review is not a result approval.
