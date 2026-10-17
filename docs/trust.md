# Optional signed ledger checkpoints

Phase 3 adds `trust checkpoint` and `trust verify` alongside the existing local
ledger. SQLite schema 1, workflow protocol 2, legacy events, audits and task gates
retain their meaning. The runtime still uses the Python standard library;
these optional commands require OpenSSH `ssh-keygen` with SSHSIG support.

## Operator trust contract

An operator owns the signing key, exact signer principal, allowed-signers policy,
optional revoked-keys/KRL file and the latest checkpoint SHA256 pin. All paths
must be outside the project, without symlinks or `..`. Keep keys and policy/pins
in an independently protected location. UADOS never enrolls a key, generates a
production key, copies private keys into evidence or authenticates agent labels.

Store the returned digest through a trusted channel outside this workspace.
Passing a digest read from the same attacker-controlled bundle supplies no
independent anchor. The allowed-signers policy authorizes a principal/key and may
restrict its namespace; an authorized signature is more than an unvalidated
signature-structure check. Key rotation is an operator action: update a versioned
external policy, use the new key, issue a new bundle, and distribute its new pin.
Revocation applies the supplied *current* policy, including an OpenSSH revoked
public-key list or KRL. Historical policy evaluation requires retaining and
explicitly choosing that policy externally; there is no trusted timestamp.

The fixed namespace is `uados-checkpoint@uados.local`. The payload binds format,
version, principal, first event hash (project identity), event sequence/head hash,
full-state digest and a signed audit assertion. It does not sign each contributor
action or authenticate model/provider independence.

## Create and verify

The paths below are illustrative external operator paths. Supply your existing
key and authorized policy; no key is created by these commands.

```sh
python3 scripts/uados.py --project . trust checkpoint \
  --output /secure/uados/checkpoint-001 --principal alice@example.org \
  --key /secure/keys/uados-signing
python3 scripts/uados.py --project . trust verify \
  --bundle /secure/uados/checkpoint-001 --principal alice@example.org \
  --expected-sha256 EXTERNALLY_TRUSTED_SHA256 \
  --allowed-signers /secure/policies/uados-allowed-signers \
  --revocations /secure/policies/uados-revoked-keys --require-current
```

Allowed-signers format is the standard OpenSSH format, for example:

```text
alice@example.org namespaces="uados-checkpoint@uados.local" ssh-ed25519 PUBLIC_KEY_BASE64
```

Creation performs the normal current audit, rejects failed current integrity,
then reacquires the existing project lock and requires the audit head/count to
match the loaded ledger. It holds the lock through signing and publication. An
intervening CLI mutation fails the capture instead of nesting locks or asserting
an inconsistent observation. Locks do not stop arbitrary editor/OS writes.

No ledger event is appended. A new external directory contains `checkpoint.json`,
`checkpoint.json.sig` and a final `COMPLETE` marker with both content hashes.
Signing succeeds in staging before exclusive directory creation. Concurrent
creators have one winner; an existing destination is never overwritten. If disk
publication fails after exclusive creation, the incomplete directory remains for
operator inspection and fails verification. Choose a new output path to retry.
Completion markers establish bundle completeness, not authorization.

Verification snapshots the exact supplied public policy/revocation and signature
bytes into a disposable private directory, verifies the authorized signature and
fixed namespace, parses strict canonical JSON and checks the externally pinned
digest against the exact message. It then validates the whole ledger hash chain
and matches the checkpoint's project/sequence/head/state to that event. Inputs
are size bounded; missing tools, malformed inputs, timeouts, wrong principals,
unauthorized/revoked keys and altered outputs produce explicit failure.

## Interpret the result

`signature_verified` and `ledger_binding_verified` describe the authorized
checkpoint and its ledger prefix. `covers_current_head` is false if valid later
events exist; `--require-current` rejects that case. A trusted newest external pin
rejects a truncated or rehashed local history. Replaying both an old legitimate
bundle *and its old trusted pin* against a truncated old workspace can succeed:
this tool cannot discover a globally latest head. Protect latest pins externally
when rollback resistance matters.

`signed_audit_assertion` records the signer's observation at creation. It cannot
independently recreate old live-file availability. `current_audit` is a separate
fresh audit; edited live evidence or projections can fail it even while the old
signature remains valid. Overall `ok` and CLI exit 0 require current audit
consistency. Current failure returns exit 1; input/authorization/binding failures
return exit 2. `history_ok=false` remains visible and does not fabricate missing
legacy originals. Historical loss is compatible with a passing current audit.

This optional integration provides a cryptographic checkpoint boundary under
operator-controlled external trust. It does not establish protected operating
system storage, organizational identity enrollment, global freshness, distributed
coordination, actual provider dispatch, hosted CI or scientific validity.

## Validation and reference

`python3 -m unittest discover -s tests -p test_trust.py -v` uses real temporary
Ed25519 signatures, authorization, revocation, rotation, namespace and tamper
checks; test keys live outside disposable fixture projects and are deleted.
Ledger forgery/truncation, historical-prefix handling, parser/path/size failures,
timeout/tool failure, audit capture races and concurrent output publication have
separate checks. A missing OpenSSH executable is reported as an explicit test
skip, not passing cryptographic validation; commands fail unavailable.

API reference: [official OpenBSD ssh-keygen manual](https://man.openbsd.org/ssh-keygen.1),
checked on 2026-10-13, including `-Y sign`, authorized `-Y verify`, namespaces,
allowed-signers policies and `-r` revocations. Host behavior is verified by
executed tests separately from this reference.
