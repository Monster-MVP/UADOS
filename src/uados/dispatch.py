"""Provider-neutral dispatch receipts.

Only the deterministic local ``fake`` adapter is implemented.  It performs no
shell, network or credential lookup and never mutates the UADOS ledger.
"""

import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from .storage import UadosError, canonical, now, safe_path

REQUEST_FORMAT = "uados-dispatch-request"
RECEIPT_FORMAT = "uados-dispatch-receipt"
VERSION = 1
REQUEST_LIMIT = 64 * 1024
RECEIPT_LIMIT = 128 * 1024
ADAPTER = "uados.fake.v1"


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise UadosError("Dispatch JSON contains a duplicate key.")
        result[key] = value
    return result


def _parse(raw, limit, label):
    if not raw or len(raw) > limit:
        raise UadosError("Dispatch %s exceeds its size limit." % label)
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if not isinstance(value, dict) or (canonical(value) + "\n").encode("utf-8") != raw:
            raise UadosError("Dispatch %s must be canonical JSON with one trailing newline." % label)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise UadosError("Dispatch %s must be canonical UTF-8 JSON." % label) from exc
    return value


def _read(path, limit, label):
    try:
        if path.stat().st_size > limit:
            raise UadosError("Dispatch %s exceeds its size limit." % label)
        with path.open("rb") as stream:
            raw = stream.read(limit + 1)
        if len(raw) > limit or path.stat().st_size != len(raw):
            raise UadosError("Dispatch %s changed or exceeds its size limit." % label)
    except OSError as exc:
        raise UadosError("Dispatch %s is unavailable." % label) from exc
    return raw


def _project_file(project, relative):
    if not isinstance(relative, str) or Path(relative).is_absolute() or Path(relative).as_posix() != relative:
        raise UadosError("Dispatch request paths must be canonical project-relative paths.")
    path = safe_path(project.root, relative)
    if not path.is_file():
        raise UadosError("Dispatch request must be a file.")
    return path


def _request(project, relative):
    path = _project_file(project, relative)
    raw = _read(path, REQUEST_LIMIT, "request")
    value = _parse(raw, REQUEST_LIMIT, "request")
    if set(value) != {"format", "version", "provider", "operation", "input"}:
        raise UadosError("Dispatch request has unknown or missing fields.")
    if value["format"] != REQUEST_FORMAT or type(value["version"]) is not int or value["version"] != VERSION:
        raise UadosError("Unsupported dispatch request format or version.")
    if value["provider"] != "fake" or not isinstance(value["operation"], str) or not value["operation"] or len(value["operation"]) > 128:
        raise UadosError("Only a bounded fake provider and operation are supported.")
    return path, raw, value


def _external_path(project, value):
    path = Path(value).expanduser().absolute()
    if ".." in path.parts or path.is_relative_to(project.root) or path.resolve(strict=False).is_relative_to(project.root):
        raise UadosError("Dispatch receipt paths must be external and contain no '..'.")
    for cursor in (path,) + tuple(path.parents):
        if cursor.is_symlink():
            raise UadosError("Dispatch receipt paths must not contain symlinks.")
    return path


def _external_output(project, value):
    path = _external_path(project, value)
    if path.exists() or not path.parent.is_dir():
        raise UadosError("Dispatch receipt output must be a new file with an existing parent.")
    return path


def _exclusive_write(path, raw):
    fd, temporary = tempfile.mkstemp(prefix=".uados-dispatch-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
        if os.name == "posix":
            directory = os.open(str(path.parent), os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    except FileExistsError as exc:
        raise UadosError("Dispatch receipt already exists; never overwrite it.") from exc
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _fake(value, raw):
    input_bytes = canonical(value["input"]).encode("utf-8")
    response = {"accepted": True, "input_sha256": hashlib.sha256(input_bytes).hexdigest(), "operation": value["operation"]}
    response_raw = (canonical(response) + "\n").encode("utf-8")
    receipt = {"format": RECEIPT_FORMAT, "version": VERSION, "provider": "fake", "adapter": ADAPTER,
               "operation": value["operation"], "request_sha256": hashlib.sha256(raw).hexdigest(),
               "response": response, "response_sha256": hashlib.sha256(response_raw).hexdigest(),
               "status": "succeeded", "started_at": now(), "ended_at": now()}
    return receipt


def run_dispatch(project, request, output):
    path, raw, value = _request(project, request)
    output_path = _external_output(project, output)
    receipt = _fake(value, raw)
    receipt_raw = (canonical(receipt) + "\n").encode("utf-8")
    if len(receipt_raw) > RECEIPT_LIMIT:
        raise UadosError("Dispatch receipt exceeds its size limit.")
    _exclusive_write(output_path, receipt_raw)
    return {"provider": "fake", "adapter": ADAPTER, "status": "succeeded", "request": request,
            "receipt": str(output_path), "request_sha256": receipt["request_sha256"],
            "response_sha256": receipt["response_sha256"],
            "ledger_mutated": False,
            "claim_limit": "Local deterministic fake adapter only; no provider invocation or delivery claim."}


def verify_receipt(project, request, receipt):
    _, request_raw, request_value = _request(project, request)
    receipt_path = _external_path(project, receipt)
    if not receipt_path.is_file():
        raise UadosError("Dispatch receipt must be an external regular file.")
    value = _parse(_read(receipt_path, RECEIPT_LIMIT, "receipt"), RECEIPT_LIMIT, "receipt")
    if set(value) != {"format", "version", "provider", "adapter", "operation", "request_sha256", "response", "response_sha256", "status", "started_at", "ended_at"}:
        raise UadosError("Dispatch receipt has unknown or missing fields.")
    if (value["format"] != RECEIPT_FORMAT or type(value["version"]) is not int or value["version"] != VERSION
            or value["provider"] != "fake" or value["adapter"] != ADAPTER or value["status"] != "succeeded"
            or value["operation"] != request_value["operation"]):
        raise UadosError("Dispatch receipt identity does not match the fake adapter contract.")
    if (not isinstance(value["started_at"], str) or not isinstance(value["ended_at"], str)
            or not value["started_at"] or not value["ended_at"]
            or len(value["started_at"]) > 64 or len(value["ended_at"]) > 64):
        raise UadosError("Dispatch receipt timestamps are invalid or unbounded.")
    try:
        started = datetime.fromisoformat(value["started_at"])
        ended = datetime.fromisoformat(value["ended_at"])
        if started.utcoffset() is None or ended.utcoffset() is None or ended < started:
            raise ValueError("Receipt time requires an offset and ordered observations")
    except ValueError as exc:
        raise UadosError("Dispatch receipt timestamps need timezone offsets and ordered observations.") from exc
    if value["request_sha256"] != hashlib.sha256(request_raw).hexdigest():
        raise UadosError("Dispatch receipt request bytes differ from the supplied request.")
    response_raw = (canonical(value["response"]) + "\n").encode("utf-8")
    if not isinstance(value["response"], dict) or value["response_sha256"] != hashlib.sha256(response_raw).hexdigest():
        raise UadosError("Dispatch receipt response bytes are invalid or tampered.")
    expected = _fake(request_value, request_raw)
    expected["started_at"], expected["ended_at"] = value["started_at"], value["ended_at"]
    if value != expected:
        raise UadosError("Dispatch receipt does not match deterministic fake output.")
    return {"verified": True, "provider": "fake", "adapter": ADAPTER, "request": request,
            "receipt": str(receipt_path), "request_sha256": value["request_sha256"],
            "response_sha256": value["response_sha256"], "ledger_mutated": False,
            "claim_limit": "Verification covers local fake bytes only; no provider identity or delivery claim."}
