"""One transactional ledger; exported JSON and Markdown are rebuildable views."""

import contextlib
import hashlib
import json
import os
import re
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path


class UadosError(Exception):
    """A user-correctable workflow or integrity error."""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def file_hash(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".uados-write-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if os.name == "posix":
            directory_fd = os.open(str(path.parent), os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextlib.contextmanager
def project_lock(root):
    """Keep the inode stable; kernel releases the lock on process exit."""
    lock_path = root / ".uados" / "lock"
    if lock_path.is_symlink():
        raise UadosError("The project lock must not be a symlink.")
    with lock_path.open("a+b") as stream:
        if os.name == "posix":
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        else:
            import msvcrt

            stream.seek(0)
            if not stream.read(1):
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        try:
            yield
        finally:
            if os.name == "posix":
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            else:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


@contextlib.contextmanager
def connect(root):
    path = root / ".uados" / "ledger.sqlite3"
    if path.is_symlink():
        raise UadosError("The ledger must not be a symlink.")
    connection = sqlite3.connect(str(path), timeout=30)
    connection.execute("PRAGMA synchronous=FULL")
    try:
        yield connection
    finally:
        connection.close()


def create_schema(connection):
    connection.executescript(
        "CREATE TABLE state (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL);"
        "CREATE TABLE events (sequence INTEGER PRIMARY KEY, value TEXT NOT NULL);"
    )


def load_ledger(connection):
    try:
        check = connection.execute("PRAGMA quick_check").fetchone()[0]
        if check != "ok":
            raise UadosError("SQLite integrity check failed: " + check)
        row = connection.execute("SELECT value FROM state WHERE id=1").fetchone()
        if row is None:
            raise UadosError("The ledger has no project state.")
        state = json.loads(row[0])
        if not isinstance(state, dict):
            raise UadosError("Project state must be a JSON object.")
        if state.get("schema_version") != 1:
            raise UadosError("Unsupported schema version; use a compatible UADOS release.")
        if state.get("protocol_version", 1) not in {1, 2}:
            raise UadosError("Unsupported workflow protocol version.")
        if state.get("protocol_version", 1) == 2:
            from .protocol import COLLECTIONS
            for key in COLLECTIONS:
                if not isinstance(state.get(key), dict):
                    raise UadosError("Invalid protocol2 state field: " + key)
        for key, expected in (("tasks", dict), ("sessions", dict), ("experiments", dict), ("counters", dict), ("decisions", list), ("notes", list), ("handovers", list), ("mode_detection", dict), ("name", str), ("objective", str), ("phase", str)):
            if not isinstance(state.get(key), expected):
                raise UadosError("Invalid project state field: " + key)
        events = []
        previous = "0" * 64
        for sequence, raw in connection.execute("SELECT sequence,value FROM events ORDER BY sequence"):
            event = json.loads(raw)
            if not isinstance(event, dict):
                raise UadosError("Event %d must be a JSON object." % sequence)
            claimed_hash = event.pop("hash")
            if sequence != len(events) + 1 or event["sequence"] != sequence:
                raise UadosError("The event sequence is broken.")
            if event["previous_hash"] != previous or digest(event) != claimed_hash:
                raise UadosError("The event chain is inconsistent at event %d." % sequence)
            event["hash"] = claimed_hash
            previous = claimed_hash
            events.append(event)
        if not events or canonical(events[-1]["state"]) != canonical(state):
            raise UadosError("The state disagrees with the committed event history.")
        return state, events
    except (sqlite3.DatabaseError, ValueError, KeyError, TypeError) as exc:
        raise UadosError("Unreadable ledger: %s" % exc) from exc


def event_header(events, kind, actor, summary):
    return {
        "sequence": len(events) + 1,
        "occurred_at": now(),
        "kind": kind,
        "actor": actor,
        "summary": summary,
        "previous_hash": events[-1]["hash"] if events else "0" * 64,
    }


def commit_event(connection, state, header):
    event = dict(header, state=state)
    event["hash"] = digest(event)
    connection.execute("INSERT INTO events(sequence,value) VALUES (?,?)", (event["sequence"], canonical(event)))
    connection.execute("INSERT OR REPLACE INTO state(id,value) VALUES (1,?)", (canonical(state),))
    connection.commit()
    return event


IGNORED_PARTS = {".git", ".uados", "__pycache__", "node_modules", ".venv", "venv", ".pytest_cache", ".DS_Store"}
GENERATED_PATHS = {"PROJECT_STATE.md", "DEVELOPMENT_LOG.md", "DECISION_RECORD.md", "SESSION_HANDOVER.md", "PROJECT_MEMORY/tasks.md", "PROJECT_MEMORY/knowledge.md", "RESEARCH_MANAGEMENT/experiments.md"}
GENERATED_PATHS.update({"CONSENSUS_DECISION.md", "SYSTEM_IMPROVEMENT_LOG.md", "MULTI_AGENT_SYSTEM/role_plans.md", "RESEARCH_MANAGEMENT/NOVELTY_AUDIT.md", "RESEARCH_MANAGEMENT/LITERATURE_GAP_ANALYSIS.md", "RESEARCH_MANAGEMENT/RESEARCH_DECISION_RECORD.md", "RESEARCH_MANAGEMENT/HYPOTHESES.md"})


def safe_path(root, relative, allow_missing=False):
    if not isinstance(relative, (str, Path)) or not str(relative).strip():
        raise UadosError("Project paths must be nonempty strings or Path objects.")
    raw = Path(relative)
    if raw.is_absolute() or ".." in raw.parts:
        raise UadosError("Use a path inside the project, without '..': %s" % relative)
    target = root / raw
    cursor = root
    for part in raw.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise UadosError("Symlinks are not supported in project records: %s" % relative)
    if not target.resolve().is_relative_to(root.resolve()):
        raise UadosError("Path escapes the project: %s" % relative)
    if not allow_missing and not target.exists():
        raise UadosError("Project file is unavailable: %s" % relative)
    return target


def evidence_files(root, paths):
    records = []
    for relative in paths:
        path = safe_path(root, relative)
        if not path.is_file():
            raise UadosError("Evidence must be a file: %s" % relative)
        content = path.read_bytes()
        checksum = hashlib.sha256(content).hexdigest()
        snapshot = ".uados/evidence/sha256/" + checksum
        target = safe_path(root, snapshot, allow_missing=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if not target.is_file() or target.read_bytes() != content:
                raise UadosError("Existing evidence snapshot is corrupt: " + snapshot)
        else:
            fd, temporary = tempfile.mkstemp(prefix=".uados-write-", dir=str(target.parent))
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                # Publish only a fully flushed file, without replacing an
                # existing object. Concurrent equal writers are idempotent.
                try:
                    os.link(temporary, target)
                except FileExistsError:
                    if not target.is_file() or target.read_bytes() != content:
                        raise UadosError("Existing evidence snapshot is corrupt: " + snapshot)
                if os.name == "posix":
                    descriptor = os.open(str(target.parent), os.O_RDONLY)
                    try:
                        os.fsync(descriptor)
                    finally:
                        os.close(descriptor)
            finally:
                os.unlink(temporary)
        records.append({"path": path.relative_to(root).as_posix(), "sha256": checksum, "bytes": len(content), "snapshot": snapshot})
    return records


def snapshot_problems(root, record):
    """Promised snapshots are immutable integrity inputs, including history."""
    if "snapshot" not in record:
        return []  # Older records never promised archived bytes.
    expected = ".uados/evidence/sha256/" + record["sha256"]
    if record["snapshot"] != expected or not re.fullmatch(r"[0-9a-f]{64}", record["sha256"]):
        return ["Invalid evidence snapshot binding: " + record["path"]]
    try:
        path = safe_path(root, expected)
        if not path.is_file() or path.stat().st_size != record["bytes"] or file_hash(path) != record["sha256"]:
            return ["Evidence snapshot corrupt: " + expected]
    except UadosError as exc:
        return ["Evidence snapshot unavailable: " + str(exc)]
    return []


def scope_snapshot(root, scopes):
    result = {}
    for relative in scopes:
        path = safe_path(root, relative, allow_missing=True)
        if not path.exists():
            result[Path(relative).as_posix()] = "missing"
            continue
        files = [path] if path.is_file() else sorted(path.rglob("*"))
        for item in files:
            relative_path = item.relative_to(root)
            if (any(part in IGNORED_PARTS for part in relative_path.parts)
                    or relative_path.as_posix() in GENERATED_PATHS
                    or relative_path.parts[:2] == ("PROJECT_MEMORY", "session_reports")
                    or (relative_path.parent.as_posix() == "CHANGE_REQUESTS" and re.fullmatch(r"CR[0-9]+\.md", item.name))
                    or item.name.startswith(".uados-write-")):
                continue
            safe_path(root, relative_path)
            if item.is_file():
                result[relative_path.as_posix()] = file_hash(item)
    return result
