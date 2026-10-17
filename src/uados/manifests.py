"""Strict, opt-in recursive evidence manifests.

Manifest support is deliberately a thin layer over the existing content-addressed
evidence store.  Ordinary evidence remains opaque and legacy records are never
reinterpreted.
"""

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict

from .storage import (GENERATED_PATHS, UadosError, canonical, file_hash,
                      safe_path)

SUFFIX = ".uados-manifest.json"
FORMAT = "uados-evidence-manifest"
VERSION = 1
MANIFEST_LIMIT = 1024 * 1024
FILE_LIMIT = 16 * 1024 * 1024
AGGREGATE_LIMIT = 128 * 1024 * 1024
MAX_DEPTH = 16
MAX_NODES = 4096


def _hash(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise UadosError("Manifest hashes must be lowercase SHA256 hex strings.")
    return value


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise UadosError("Manifest JSON contains a duplicate key.")
        result[key] = value
    return result


def parse(raw):
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise UadosError("Manifest must be valid UTF-8 canonical JSON.") from exc
    if not isinstance(value, dict) or (canonical(value) + "\n").encode("utf-8") != raw:
        raise UadosError("Manifest JSON must be canonical with one trailing newline.")
    if set(value) != {"format", "version", "files"} or value["format"] != FORMAT or type(value["version"]) is not int or value["version"] != VERSION:
        raise UadosError("Unsupported manifest format, version or fields.")
    files = value["files"]
    if not isinstance(files, list) or not files:
        raise UadosError("Manifest files must be a nonempty list.")
    result = []
    seen = set()
    for item in files:
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "bytes", "kind"}:
            raise UadosError("Manifest entries have exactly path, sha256, bytes and kind.")
        path, kind = item["path"], item["kind"]
        if (not isinstance(path, str) or not path or "\\" in path
                or Path(path).is_absolute() or ".." in Path(path).parts
                or "." in Path(path).parts or Path(path).as_posix() != path):
            raise UadosError("Manifest paths must be canonical project-relative POSIX paths.")
        if path in seen:
            raise UadosError("Manifest contains a duplicate path: " + path)
        seen.add(path)
        if (not isinstance(kind, str) or kind not in {"file", "manifest"}
                or (kind == "manifest") != path.endswith(SUFFIX)):
            raise UadosError("Manifest entry kind does not match its reserved suffix: " + path)
        if type(item["bytes"]) is not int or item["bytes"] < 0:
            raise UadosError("Manifest entry bytes must be a nonnegative integer.")
        _hash(item["sha256"])
        result.append({"path": path, "sha256": item["sha256"], "bytes": item["bytes"], "kind": kind})
    return result


def _read(path, limit):
    try:
        before = path.stat().st_size
        if before > limit:
            raise UadosError("Manifest dependency exceeds its size limit: " + str(path))
        with path.open("rb") as stream:
            value = stream.read(limit + 1)
        after = path.stat().st_size
    except OSError as exc:
        raise UadosError("Manifest dependency is unavailable: " + str(path)) from exc
    if len(value) > limit or after != before:
        raise UadosError("Manifest dependency exceeds its size limit: " + str(path))
    return value


def _check_path(root, relative):
    if (relative in GENERATED_PATHS or relative.startswith(".uados/")
            or relative == ".uados" or relative == ".git" or relative.startswith(".git/")
            or relative.startswith("PROJECT_MEMORY/session_reports/")
            or (Path(relative).parent.as_posix() == "CHANGE_REQUESTS"
                and re.fullmatch(r"CR[0-9]+\.md", Path(relative).name))):
        raise UadosError("Manifest cannot depend on generated or metadata paths: " + relative)
    path = safe_path(root, relative)
    if not path.is_file():
        raise UadosError("Manifest dependency must be a file: " + relative)
    return path


def _record(relative, content, kind):
    return {"path": relative, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content), "kind": kind}


def _publish(root, relative, content):
    checksum = hashlib.sha256(content).hexdigest()
    target = safe_path(root, ".uados/evidence/sha256/" + checksum, allow_missing=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if not target.is_file() or target.read_bytes() != content:
            raise UadosError("Existing evidence snapshot is corrupt: " + target.as_posix())
        return ".uados/evidence/sha256/" + checksum
    fd, temporary = tempfile.mkstemp(prefix=".uados-manifest-", dir=str(target.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, target)
        except FileExistsError:
            if target.read_bytes() != content:
                raise UadosError("Existing evidence snapshot is corrupt: " + target.as_posix())
        if os.name == "posix":
            descriptor = os.open(str(target.parent), os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return ".uados/evidence/sha256/" + checksum


def _capture_graph(root, roots):
    nodes: Dict[str, Any] = {}
    contents = {}
    active = []
    total = [0]

    def visit(relative, depth):
        if depth > MAX_DEPTH:
            raise UadosError("Manifest dependency depth exceeds the limit.")
        if relative in active:
            raise UadosError("Manifest dependency cycle detected: " + relative)
        if relative in nodes:
            return nodes[relative]
        path = _check_path(root, relative)
        is_manifest = relative.endswith(SUFFIX)
        limit = MANIFEST_LIMIT if is_manifest else FILE_LIMIT
        content = _read(path, limit)
        total[0] += len(content)
        if total[0] > AGGREGATE_LIMIT:
            raise UadosError("Manifest dependency bytes exceed the aggregate limit.")
        actual = _record(relative, content, "manifest" if is_manifest else "file")
        if len(nodes) >= MAX_NODES:
            raise UadosError("Manifest dependency node count exceeds the limit.")
        nodes[relative] = actual
        contents[relative] = content
        if is_manifest:
            active.append(relative)
            for entry in parse(content):
                child = visit(entry["path"], depth + 1)
                if child["sha256"] != entry["sha256"] or child["bytes"] != entry["bytes"] or child["kind"] != entry["kind"]:
                    raise UadosError("Manifest declaration does not match captured bytes: " + entry["path"])
            active.pop()
        return actual

    for relative in roots:
        visit(relative, 0)
    return nodes, contents


def capture_batch(root, paths):
    """Capture a batch containing manifests after validating its complete graph."""
    roots = []
    for value in paths:
        if not isinstance(value, str) or Path(value).as_posix() != value:
            raise UadosError("Evidence paths must be canonical project-relative POSIX paths.")
        roots.append(value)
    manifest_roots = [value for value in roots if value.endswith(SUFFIX)]
    if not manifest_roots:
        return None
    nodes, contents = _capture_graph(root, manifest_roots)
    # Ordinary peers join the same bounded batch and are read before publication.
    for relative in roots:
        if relative.endswith(SUFFIX):
            continue
        if relative in nodes:
            continue
        path = _check_path(root, relative)
        content = _read(path, FILE_LIMIT)
        if sum(len(v) for v in contents.values()) + len(content) > AGGREGATE_LIMIT:
            raise UadosError("Manifest dependency bytes exceed the aggregate limit.")
        node = _record(relative, content, "file")
        if relative in nodes and nodes[relative] != node:
            raise UadosError("Conflicting evidence declaration: " + relative)
        if len(nodes) >= MAX_NODES:
            raise UadosError("Manifest dependency node count exceeds the limit.")
        nodes[relative] = node
        contents[relative] = content
    # Publish only after all declarations and bytes have passed validation.
    snapshots = {relative: _publish(root, relative, content) for relative, content in contents.items()}
    result = []
    for relative in roots:
        node = nodes[relative]
        record = {"path": relative, "sha256": node["sha256"], "bytes": node["bytes"], "snapshot": snapshots[relative]}
        if node["kind"] == "manifest":
            reachable = set()
            def collect(name):
                for entry in parse(contents[name]):
                    child = entry["path"]
                    if child in reachable:
                        continue
                    reachable.add(child)
                    if entry["kind"] == "manifest":
                        collect(child)
            collect(relative)
            deps = []
            for dep in sorted(nodes.values(), key=lambda value: (value["path"], value["sha256"])):
                if dep["path"] not in reachable:
                    continue
                item = dict(dep, snapshot=snapshots[dep["path"]])
                deps.append(item)
            record.update(kind="manifest", manifest_version=VERSION, dependencies=deps)
        result.append(record)
    return result


def _stored_map(record):
    deps = record.get("dependencies")
    if type(record.get("manifest_version")) is not int or record.get("manifest_version") != VERSION or not isinstance(deps, list):
        raise UadosError("Manifest evidence dependency metadata is malformed: " + record.get("path", "?"))
    result = {}
    for item in deps:
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "bytes", "kind", "snapshot"}:
            raise UadosError("Manifest dependency metadata is malformed.")
        key = item["path"]
        if (not isinstance(key, str) or Path(key).as_posix() != key
                or ".." in Path(key).parts or "\\" in key):
            raise UadosError("Manifest dependency metadata has an invalid path.")
        if (key in result or not isinstance(item["kind"], str)
                or item["kind"] not in {"file", "manifest"}
                or (item["kind"] == "manifest") != key.endswith(SUFFIX)):
            raise UadosError("Manifest dependency metadata is conflicting.")
        _hash(item["sha256"])
        expected_snapshot = ".uados/evidence/sha256/" + item["sha256"]
        if (type(item["bytes"]) is not int or item["bytes"] < 0
                or item["snapshot"] != expected_snapshot):
            raise UadosError("Manifest dependency metadata has invalid types.")
        result[key] = item
    if list(result) != sorted(result):
        raise UadosError("Manifest dependency metadata is not deterministically sorted.")
    return result


def validate_record(root, record):
    """Validate a stored manifest closure from its immutable snapshots."""
    if record.get("manifest_version") is None:
        return []
    errors = []
    try:
        root_path = record.get("path", "")
        if (not isinstance(root_path, str) or Path(root_path).is_absolute()
                or Path(root_path).as_posix() != root_path
                or not root_path.endswith(SUFFIX) or ".." in Path(root_path).parts
                or "\\" in root_path or root_path.startswith(".uados/")
                or root_path in GENERATED_PATHS
                or root_path.startswith("PROJECT_MEMORY/session_reports/")
                or (Path(root_path).parent.as_posix() == "CHANGE_REQUESTS"
                    and re.fullmatch(r"CR[0-9]+\.md", Path(root_path).name))
                or record.get("kind") != "manifest"
                or record.get("snapshot") != ".uados/evidence/sha256/" + record.get("sha256", "")
                or type(record.get("bytes")) is not int or record["bytes"] < 0):
            raise UadosError("Manifest root evidence metadata is malformed: " + str(root_path))
        mapping = _stored_map(record)
        root_snapshot = safe_path(root, record["snapshot"])
        raw = _read(root_snapshot, MANIFEST_LIMIT)
        if len(raw) != record.get("bytes") or hashlib.sha256(raw).hexdigest() != record.get("sha256"):
            raise UadosError("Manifest root snapshot is corrupt: " + record.get("path", "?"))
        declared = parse(raw)
        seen = set()
        active = []
        total = [len(raw)]

        def walk(manifest_path, entries, depth):
            if depth > MAX_DEPTH or manifest_path in active:
                raise UadosError("Manifest dependency cycle or depth limit detected.")
            active.append(manifest_path)
            expected_children = set()
            for entry in entries:
                expected_children.add(entry["path"])
                item = mapping.get(entry["path"])
                if item is None or item["sha256"] != entry["sha256"] or item["bytes"] != entry["bytes"] or item["kind"] != entry["kind"]:
                    raise UadosError("Archived manifest closure differs from stored dependencies: " + entry["path"])
                if entry["path"] in seen:
                    continue
                seen.add(entry["path"])
                snapshot = safe_path(root, item["snapshot"])
                child = _read(snapshot, MANIFEST_LIMIT if item["kind"] == "manifest" else FILE_LIMIT)
                if hashlib.sha256(child).hexdigest() != item["sha256"] or len(child) != item["bytes"]:
                    raise UadosError("Manifest dependency snapshot is corrupt: " + entry["path"])
                total[0] += len(child)
                if len(seen) > MAX_NODES or total[0] > AGGREGATE_LIMIT:
                    raise UadosError("Manifest dependency closure exceeds its bounds.")
                if item["kind"] == "manifest":
                    walk(entry["path"], parse(child), depth + 1)
            if expected_children and not expected_children.issubset(mapping):
                raise UadosError("Manifest dependency closure is incomplete.")
            active.pop()

        walk(record["path"], declared, 0)
        if set(mapping) != seen:
            raise UadosError("Manifest dependency closure contains extra or unreachable entries.")
    except (UadosError, KeyError, OSError, TypeError, ValueError) as exc:
        errors.append(str(exc))
    return errors
