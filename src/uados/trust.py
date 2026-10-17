"""Optional SSHSIG checkpoints; trust policies and keys stay outside the project.

Signatures attest a ledger prefix and a signer's audit observation. They do not
enroll agent identities, supply trusted timestamps or discover a global head.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .storage import UadosError, canonical, connect, digest, load_ledger, now, project_lock

NAMESPACE = "uados-checkpoint@uados.local"
LIMIT = 256 * 1024
POLICY_LIMIT = 1024 * 1024
TIMEOUT = 15
FIELDS = {"format", "version", "namespace", "principal", "project_id", "sequence", "head_hash", "state_sha256", "created_at", "audit"}


def _principal(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.@+\-]{0,127}", value):
        raise UadosError("Checkpoint principal must be an exact non-pattern identity (1-128 characters).")
    return value


def _hash(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise UadosError("Checkpoint digests must be lowercase SHA256 hex strings.")
    return value


def _external(project, value, file=False):
    path = Path(value).expanduser().absolute()
    if ".." in path.parts:
        raise UadosError("External trust paths must not contain '..'.")
    for cursor in (path,) + tuple(path.parents):
        if cursor.is_symlink():
            raise UadosError("External trust paths must not contain symlinks: " + str(path))
    if path.resolve().is_relative_to(project.root):
        raise UadosError("Keys, trust policies and checkpoint bundles must be outside the project.")
    if file and not path.is_file():
        raise UadosError("External trust file is unavailable: " + str(path))
    return path


def _bytes(path, limit=LIMIT):
    with path.open("rb") as stream:
        value = stream.read(limit + 1)
    if not value or len(value) > limit:
        raise UadosError("Trust input is empty or exceeds its size limit: " + path.name)
    return value


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise UadosError("Checkpoint JSON contains a duplicate key.")
        result[key] = value
    return result


def _json(raw):
    try:
        def invalid(_):
            raise ValueError("Non-finite JSON number")
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=invalid)
        if not isinstance(value, dict) or (canonical(value) + "\n").encode("utf-8") != raw:
            raise UadosError("Trust JSON must be a canonical object with one trailing newline.")
        return value
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise UadosError("Malformed trust JSON.") from exc


def _payload(raw, principal):
    value = _json(raw)
    if set(value) != FIELDS or value["format"] != "uados-checkpoint" or type(value["version"]) is not int or value["version"] != 1:
        raise UadosError("Unsupported checkpoint format, version or fields.")
    if value["namespace"] != NAMESPACE or value["principal"] != principal:
        raise UadosError("Checkpoint namespace or principal does not match verification policy.")
    if type(value["sequence"]) is not int or value["sequence"] < 1:
        raise UadosError("Checkpoint sequence must be a positive integer.")
    for name in ("project_id", "head_hash", "state_sha256"):
        _hash(value[name])
    if not isinstance(value["created_at"], str) or not value["created_at"] or len(value["created_at"]) > 128:
        raise UadosError("Checkpoint needs a bounded signer-asserted creation time.")
    audit = value["audit"]
    if not isinstance(audit, dict) or set(audit) != {"current_ok", "history_ok", "lost_evidence", "warnings"}:
        raise UadosError("Invalid checkpoint audit assertion fields.")
    if audit["current_ok"] is not True or type(audit["history_ok"]) is not bool:
        raise UadosError("Checkpoint must attest successful current consistency with explicit history status.")
    if not isinstance(audit["warnings"], list) or any(not isinstance(v, str) for v in audit["warnings"]):
        raise UadosError("Checkpoint audit warnings must be strings.")
    if not isinstance(audit["lost_evidence"], list):
        raise UadosError("Checkpoint historical loss must be a list.")
    for record in audit["lost_evidence"]:
        if not isinstance(record, dict) or set(record) != {"path", "sha256"} or not isinstance(record["path"], str) or not record["path"]:
            raise UadosError("Invalid checkpoint historical loss record.")
        _hash(record["sha256"])
    if audit["history_ok"] != (not audit["lost_evidence"]):
        raise UadosError("Checkpoint history status disagrees with its loss assertion.")
    return value


def _run(arguments, input_bytes=None):
    executable = shutil.which("ssh-keygen")
    if not executable:
        raise UadosError("Trust commands require OpenSSH ssh-keygen with SSHSIG support.")
    try:
        if input_bytes is None:
            result = subprocess.run(
                [executable] + arguments,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=TIMEOUT,
                start_new_session=(os.name == "posix"),
            )
        else:
            result = subprocess.run(
                [executable] + arguments,
                input=input_bytes,
                capture_output=True,
                timeout=TIMEOUT,
                start_new_session=(os.name == "posix"),
            )
    except subprocess.TimeoutExpired as exc:
        raise UadosError("OpenSSH trust operation timed out.") from exc
    except OSError as exc:
        raise UadosError("OpenSSH trust operation could not start.") from exc
    if result.returncode:
        # Do not expose arbitrary tool diagnostics/key prompts in project logs.
        raise UadosError("OpenSSH signing/authorized verification failed (exit %d)." % result.returncode)
    return result


def _write(path, raw):
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _fsync_dir(path):
    if os.name == "posix":
        descriptor = os.open(str(path), os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def create_checkpoint(project, output, principal, key):
    """No ledger mutation; output is exclusive and marked complete last."""
    principal = _principal(principal)
    key = _external(project, key, file=True)
    output = _external(project, output)
    if output.exists() or not output.parent.is_dir() or project.root.is_relative_to(output):
        raise UadosError("Checkpoint output must be a new external directory with an existing parent.")
    audit = project.audit()
    if not audit["ok"]:
        raise UadosError("Current audit failed; no checkpoint can be published.")
    with project_lock(project.root), connect(project.root) as connection:
        state, events = load_ledger(connection)
        if audit["event_count"] != len(events) or audit["head_hash"] != events[-1]["hash"]:
            raise UadosError("Ledger changed between audit and checkpoint capture; retry the audit.")
        value = {"format": "uados-checkpoint", "version": 1, "namespace": NAMESPACE,
                 "principal": principal, "project_id": events[0]["hash"], "sequence": len(events),
                 "head_hash": events[-1]["hash"], "state_sha256": digest(state), "created_at": now(),
                 "audit": {"current_ok": True, "history_ok": audit["history_ok"],
                           "lost_evidence": [{"path": r["path"], "sha256": r["sha256"]} for r in audit["historical_evidence_drift"]],
                           "warnings": audit["warnings"]}}
        raw = (canonical(value) + "\n").encode("utf-8")
        if len(raw) > LIMIT:
            raise UadosError("Checkpoint audit assertion exceeds the size limit.")
        _payload(raw, principal)
        with tempfile.TemporaryDirectory(prefix=".uados-checkpoint-", dir=str(output.parent)) as temporary:
            staging = Path(temporary)
            message = staging / "checkpoint.json"
            _write(message, raw)
            _run(["-Y", "sign", "-f", str(key), "-n", NAMESPACE, str(message)])
            signature = _bytes(staging / "checkpoint.json.sig")
            # OpenSSH closing its output does not promise fsync. Publish the
            # exact signature bytes through our own flushed immutable copy.
            durable_signature = staging / "signature-durable"
            _write(durable_signature, signature)
            pin = hashlib.sha256(raw).hexdigest()
            marker = {"checkpoint_sha256": pin, "signature_sha256": hashlib.sha256(signature).hexdigest()}
            _write(staging / "COMPLETE", (canonical(marker) + "\n").encode("utf-8"))
            # mkdir is the exclusive ownership boundary. A loser never cleans
            # the winner, and rename cannot silently replace an empty target.
            try:
                output.mkdir(mode=0o700)
            except FileExistsError as exc:
                raise UadosError("Checkpoint output already exists; never overwrite a bundle.") from exc
            # Any publication failure leaves a clearly incomplete directory;
            # do not delete a directory another local writer could have changed.
            for name in ("checkpoint.json", "checkpoint.json.sig", "COMPLETE"):
                source = durable_signature if name == "checkpoint.json.sig" else staging / name
                os.link(source, output / name)
                _fsync_dir(output)
            _fsync_dir(output.parent)
    return {"created": True, "bundle": str(output), "checkpoint_sha256": pin,
            "sequence": value["sequence"], "head_hash": value["head_hash"],
            "signed_audit_assertion": value["audit"],
            "authorization": "Verify separately using an externally trusted digest and allowed-signers policy."}


def verify_checkpoint(project, bundle, principal, expected_sha256, allowed_signers, revocations=None, require_current=False):
    principal = _principal(principal)
    pin = _hash(expected_sha256)
    bundle = _external(project, bundle)
    if not bundle.is_dir():
        raise UadosError("External checkpoint bundle is unavailable.")
    message = _bytes(_external(project, bundle / "checkpoint.json", file=True))
    signature = _bytes(_external(project, bundle / "checkpoint.json.sig", file=True))
    marker = _json(_bytes(_external(project, bundle / "COMPLETE", file=True)))
    if marker != {"checkpoint_sha256": hashlib.sha256(message).hexdigest(), "signature_sha256": hashlib.sha256(signature).hexdigest()}:
        raise UadosError("Checkpoint bundle is incomplete or its completion marker changed.")
    if hashlib.sha256(message).hexdigest() != pin:
        raise UadosError("Checkpoint differs from the externally trusted SHA256 pin.")
    policy = _bytes(_external(project, allowed_signers, file=True), POLICY_LIMIT)
    revoked = _bytes(_external(project, revocations, file=True), POLICY_LIMIT) if revocations is not None else None
    # Verify exactly the bytes read, never a mutable policy/signature pathname.
    with tempfile.TemporaryDirectory(prefix="uados-verify-") as temporary:
        directory = Path(temporary)
        _write(directory / "allowed", policy)
        _write(directory / "signature", signature)
        command = ["-Y", "verify", "-f", str(directory / "allowed"), "-I", principal,
                   "-n", NAMESPACE, "-s", str(directory / "signature")]
        if revoked is not None:
            _write(directory / "revoked", revoked)
            command += ["-r", str(directory / "revoked")]
        _run(command, message)
    value = _payload(message, principal)
    with project_lock(project.root), connect(project.root) as connection:
        state, events = load_ledger(connection)
        sequence = value["sequence"]
        if sequence > len(events) or value["project_id"] != events[0]["hash"]:
            raise UadosError("Checkpoint project or sequence is missing from this ledger.")
        event = events[sequence - 1]
        if value["head_hash"] != event["hash"] or value["state_sha256"] != digest(event["state"]):
            raise UadosError("Ledger prefix/state differs from the authorized checkpoint.")
        current = sequence == len(events)
        if require_current and not current:
            raise UadosError("Checkpoint covers a historical prefix, not the current ledger head.")
        observed_head = events[-1]["hash"]
    audit = project.audit()
    if audit["head_hash"] != observed_head:
        raise UadosError("Ledger changed during verification; retry against stable current state.")
    return {"ok": audit["ok"], "signature_verified": True, "ledger_binding_verified": True,
            "covers_current_head": current, "sequence": sequence, "current_sequence": audit["event_count"],
            "checkpoint_sha256": pin, "principal": principal,
            "allowed_signers_sha256": hashlib.sha256(policy).hexdigest(),
            "revocations_sha256": hashlib.sha256(revoked).hexdigest() if revoked is not None else None,
            "signed_audit_assertion": value["audit"], "current_audit": audit,
            "trust_limit": "Caller-selected external pin/key policy. Historical audit is signer attestation; no global freshness, trusted timestamp or agent enrollment."}
