"""Project lifecycle, context gates, task ownership and durable review records."""

import json
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .context import (REQUIRED_DIRECTORIES, context_bundle, maintained_context,
                      render_views, report_markdown, understanding_report)
from .storage import (UadosError, atomic_write, canonical, commit_event, connect,
                      create_schema, digest, evidence_files, event_header,
                      file_hash, load_ledger, now, project_lock, safe_path,
                      scope_snapshot, snapshot_problems)
from .protocol import all_evidence, current_evidence, extend_state, task_version, version


def require_text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise UadosError(label + " must contain meaningful text.")
    return value.strip()


def identify_mode(root):
    software, research = [], []
    excluded = set(REQUIRED_DIRECTORIES) | {".git", ".uados", ".venv", "node_modules", "__pycache__"}
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(part in excluded for part in relative.parts) or path.is_symlink():
            continue
        if path.is_file():
            if path.suffix in {".py", ".js", ".ts", ".go", ".rs", ".java", ".cpp"} or path.name in {"package.json", "pyproject.toml", "Cargo.toml"}:
                software.append(relative.as_posix())
            if path.suffix in {".ipynb", ".bib", ".tex"} or any(part.lower() in {"experiments", "simulation", "datasets", "literature"} for part in relative.parts):
                research.append(relative.as_posix())
    mode = "hybrid" if software and research else "research" if research else "software"
    return {"selected": mode, "confidence": "heuristic" if software or research else "default-low", "software_evidence": software[:20], "research_evidence": research[:20], "override": False}


def initial_state(name, objective, mode, detection, protocol_version=2):
    state = {"schema_version": 1, "protocol_version": protocol_version, "name": name, "objective": objective, "mode": mode,
            "mode_detection": detection, "phase": "planning", "tasks": {}, "sessions": {},
            "decisions": [], "notes": [], "experiments": {}, "handovers": [],
            "counters": {}, "review_quorum": 1}
    if protocol_version == 2:
        extend_state(state)
    return state


def next_id(state, prefix):
    state["counters"][prefix] = state["counters"].get(prefix, 0) + 1
    return "%s%06d" % (prefix, state["counters"][prefix])


def projection_map(state, events):
    result = render_views(state, events)
    result[".uados/state.json"] = json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    result[".uados/events.jsonl"] = "".join(canonical(e) + "\n" for e in events)
    for session in state["sessions"].values():
        for report in session["reports"]:
            result[report["path"]] = report_markdown(report["content"], report["hash"])
    return result


def projection_drift(root, state, events):
    drift = []
    for relative, content in projection_map(state, events).items():
        path = safe_path(root, relative, allow_missing=True)
        if not path.is_file() or path.read_bytes() != content.encode("utf-8"):
            drift.append(relative)
    return drift


def write_projections(root, state, events):
    for relative, content in projection_map(state, events).items():
        path = safe_path(root, relative, allow_missing=True)
        if not path.is_file() or path.read_bytes() != content.encode("utf-8"):
            atomic_write(path, content)


def check_evidence(root, records):
    problems = []
    for record in records:
        problems.extend(snapshot_problems(root, record))
        try:
            path = safe_path(root, record["path"])
            if not path.is_file() or file_hash(path) != record["sha256"]:
                problems.append("Evidence changed: " + record["path"])
        except UadosError as exc:
            problems.append(str(exc))
    return problems


def task_contributors(task):
    return {task["author"], task.get("implementer")} | set(task.get("contributors", [])) | {entry.get("agent") for entry in task["work"] if entry["kind"] == "implementation"}


class Project:
    def __init__(self, root):
        self.root = Path(root).resolve()
        if not (self.root / ".uados" / "ledger.sqlite3").is_file():
            raise UadosError("Not an initialized UADOS project: %s" % self.root)
        if (self.root / ".uados").is_symlink():
            raise UadosError("The metadata directory must not be a symlink.")

    @classmethod
    def rebuild_ledger(cls, root):
        """Recover a missing local database from a complete, validated Git export."""
        root = Path(root).resolve()
        metadata = root / ".uados"
        if not metadata.is_dir() or metadata.is_symlink():
            raise UadosError("Project metadata exports are unavailable.")
        ledger = metadata / "ledger.sqlite3"
        with project_lock(root):
            if ledger.exists() or ledger.is_symlink():
                raise UadosError("rebuild-ledger only reconstructs a missing database; it never overwrites history.")
            journal = safe_path(root, ".uados/events.jsonl")
            try:
                events = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
                if not events:
                    raise UadosError("The exported event journal is empty.")
                if not all(isinstance(event, dict) for event in events):
                    raise UadosError("Every exported event must be a JSON object.")
                state = events[-1]["state"]
                exported_state = safe_path(root, ".uados/state.json", allow_missing=True)
                if exported_state.is_file() and canonical(json.loads(exported_state.read_text(encoding="utf-8"))) != canonical(state):
                    raise UadosError("Exported state and event history disagree; recover a consistent Git revision.")
            except (ValueError, KeyError, TypeError) as exc:
                raise UadosError("Exported event history is unreadable: %s" % exc) from exc
            fd, temporary = tempfile.mkstemp(prefix=".rebuild-", suffix=".sqlite3", dir=str(metadata))
            os.close(fd)
            try:
                with sqlite3.connect(temporary) as connection:
                    create_schema(connection)
                    connection.executemany("INSERT INTO events(sequence,value) VALUES (?,?)", [(event["sequence"], canonical(event)) for event in events])
                    connection.execute("INSERT INTO state(id,value) VALUES (1,?)", (canonical(state),))
                    connection.commit()
                    recovered_state, recovered_events = load_ledger(connection)
                with open(temporary, "rb") as stream:
                    os.fsync(stream.fileno())
                os.replace(temporary, ledger)
                write_projections(root, recovered_state, recovered_events)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        return {"project": str(root), "event_count": len(events), "rebuilt": True}

    @classmethod
    def initialize(cls, root, name, objective, mode="auto", adopt=False, protocol_version=2):
        root = Path(root).resolve()
        root.mkdir(parents=True, exist_ok=True)
        name, objective = require_text(name, "Name"), require_text(objective, "Objective")
        if protocol_version not in {1, 2}:
            raise UadosError("Workflow protocol version must be 1 or 2.")
        if mode not in {"auto", "software", "research", "hybrid"}:
            raise UadosError("Unknown project mode: " + mode)
        if (root / ".uados").exists():
            raise UadosError("Metadata already exists; initialization never overwrites a project.")
        assets = Path(__file__).with_name("assets")
        files = sorted(p for p in assets.rglob("*") if p.is_file() and p.suffix in {".md", ".mdc"})
        if not files:
            raise UadosError("Scaffold assets are missing from this installation.")
        targets = {p.relative_to(assets).as_posix(): p.read_text(encoding="utf-8") for p in files}
        generated = render_views(initial_state(name, objective, "software", {}, protocol_version), [])
        targets.update({p: "" for p in generated})
        collisions = [p for p in targets if safe_path(root, p, allow_missing=True).exists()]
        if collisions and (not adopt or any(p in generated for p in collisions)):
            raise UadosError("Initialization would overwrite existing files: " + ", ".join(collisions))
        if adopt:
            for relative in collisions:
                if not (root / relative).is_file():
                    raise UadosError("A maintained scaffold file conflicts with a directory: " + relative)
                del targets[relative]
        detection = identify_mode(root)
        if mode != "auto":
            detection.update(selected=mode, override=True)
        state = initial_state(name, objective, detection["selected"], detection, protocol_version)
        state["adoption_preserved"] = collisions if adopt else []
        # mkdir is the initialization ownership claim: a concurrent initializer fails here.
        (root / ".uados").mkdir()
        for directory in REQUIRED_DIRECTORIES:
            (root / directory).mkdir(exist_ok=True)
        for relative, content in targets.items():
            if content:
                atomic_write(safe_path(root, relative, allow_missing=True), content)
        with project_lock(root), connect(root) as connection:
            create_schema(connection)
            connection.execute("BEGIN IMMEDIATE")
            event = commit_event(connection, state, event_header([], "project.init", "system", "Initialized %s in %s mode" % (name, state["mode"])))
            write_projections(root, state, [event])
        return cls(root)

    def read(self, strict=False):
        with project_lock(self.root), connect(self.root) as connection:
            state, events = load_ledger(connection)
            drift = projection_drift(self.root, state, events)
            if strict and drift:
                raise UadosError("Generated views differ from the ledger; inspect them, then run audit --repair: " + ", ".join(drift))
            return state, events, drift

    def _session(self, state, events, session_id, current=True, acknowledged=True):
        session = state["sessions"].get(session_id)
        if session is None or session["status"] != "active":
            raise UadosError("An active session is required: " + str(session_id))
        if acknowledged and not session["acknowledged"]:
            raise UadosError("Read and acknowledge the understanding report before execution.")
        if current and session["context_fingerprint"] != context_bundle(self.root, state, events)["fingerprint"]:
            raise UadosError("Project context changed. Run session refresh, read the new report, and acknowledge it.")
        return session

    def mutate(self, kind, summary, operation, session_id=None, gate=True, advance=True):
        with project_lock(self.root), connect(self.root) as connection:
            connection.execute("BEGIN IMMEDIATE")
            state, events = load_ledger(connection)
            drift = projection_drift(self.root, state, events)
            if drift:
                raise UadosError("Generated views are stale or edited. Inspect and run audit --repair: " + ", ".join(drift))
            session = self._session(state, events, session_id) if gate else state["sessions"].get(session_id)
            actor = session["agent"] if session else "system"
            result = operation(state, events, session)
            if result and result.pop("_no_event", False):
                connection.rollback()
                return result
            header = event_header(events, kind, actor, summary)
            if advance and session and session["status"] == "active":
                session["context_fingerprint"] = context_bundle(self.root, state, events + [header])["fingerprint"]
            event = commit_event(connection, state, header)
            events.append(event)
            try:
                write_projections(self.root, state, events)
            except (OSError, UnicodeError, UadosError) as exc:
                raise UadosError("Event %d committed, but projections failed. Do not repeat the action; run audit --repair. %s" % (event["sequence"], exc)) from exc
            return dict(result or {}, event_sequence=event["sequence"])

    def start_session(self, agent, runtime="other"):
        agent = require_text(agent, "Agent identity")
        from .protocol import RUNTIMES
        if runtime not in RUNTIMES:
            raise UadosError("Unsupported runtime label; use an advertised adapter or other.")
        def operation(state, events, _):
            session_id = next_id(state, "S")
            report, report_hash = understanding_report(self.root, state, events, agent)
            if version(state) >= 2:
                report["runtime"] = runtime
                report_hash = digest(report)
            path = "PROJECT_MEMORY/session_reports/%s-%s.md" % (session_id, report_hash[:12])
            state["sessions"][session_id] = {"id": session_id, "agent": agent, "runtime": runtime, "status": "active", "started_at": now(), "acknowledged": False, "context_fingerprint": report["context_fingerprint"], "reports": [{"path": path, "hash": report_hash, "content": report}]}
            return {"session": session_id, "report_hash": report_hash, "report_path": path, "report": report}
        return self.mutate("session.start", "Started session for " + agent, operation, gate=False, advance=False)

    def refresh_session(self, session_id):
        def operation(state, events, _):
            session = self._session(state, events, session_id, current=False, acknowledged=False)
            report, report_hash = understanding_report(self.root, state, events, session["agent"])
            if version(state) >= 2:
                report["runtime"] = session.get("runtime", "other")
                report_hash = digest(report)
            path = "PROJECT_MEMORY/session_reports/%s-%s.md" % (session_id, report_hash[:12])
            session.update(acknowledged=False, context_fingerprint=report["context_fingerprint"])
            if not any(r["hash"] == report_hash for r in session["reports"]):
                session["reports"].append({"path": path, "hash": report_hash, "content": report})
            # The most recently issued hash is explicit, even if a previous report is identical.
            session["current_report_hash"] = report_hash
            return {"session": session_id, "report_hash": report_hash, "report_path": path, "report": report}
        return self.mutate("session.refresh", "Refreshed " + session_id, operation, session_id, gate=False, advance=False)

    def acknowledge(self, session_id, report_hash):
        def operation(state, events, _):
            session = self._session(state, events, session_id, acknowledged=False)
            expected = session.get("current_report_hash", session["reports"][-1]["hash"])
            if report_hash != expected:
                raise UadosError("Report hash does not match the current understanding report.")
            session["acknowledged"] = True
            return {"session": session_id, "acknowledged": True}
        return self.mutate("session.acknowledge", "Acknowledged " + session_id, operation, session_id, gate=False, advance=False)

    def close_session(self, session_id, summary, next_actions, blockers=(), failed=()):
        summary = require_text(summary, "Handover summary")
        if not next_actions:
            raise UadosError("A handover requires at least one next action.")
        for value in list(next_actions) + list(blockers) + list(failed):
            require_text(value, "Handover entry")
        def operation(state, events, _):
            session = self._session(state, events, session_id, current=False, acknowledged=False)
            released = []
            for task in state["tasks"].values():
                if task.get("owner") == session_id:
                    released.append(task["id"])
                    task.update(status="pending", owner=None, lease_until=None)
                    task["work"].append({"kind": "handover", "summary": summary, "at": now(), "agent": session["agent"]})
            session.update(status="closed", closed_at=now())
            state["handovers"].append({"session": session_id, "agent": session["agent"], "at": now(), "summary": summary, "next": list(next_actions), "blockers": list(blockers), "failed": list(failed), "released": released})
            if version(state) >= 2:
                state["handovers"][-1]["project_snapshot"] = {"phase": state["phase"], "mode": state["mode"],
                      "completed_work": [t["id"] + ": " + t["title"] for t in state["tasks"].values() if t["status"] == "done"],
                      "remaining_tasks": [t["id"] + ": " + t["title"] for t in state["tasks"].values() if t["status"] != "done"],
                      "known_problems": [t["blocker"] for t in state["tasks"].values() if t.get("blocker")],
                      "important_decisions": [{k: d[k] for k in ("id", "decision", "reason", "status")} for d in state["decisions"]],
                      "runtime": session.get("runtime", "other")}
            return {"session": session_id, "closed": True, "released": released}
        return self.mutate("session.close", summary, operation, session_id, gate=False)

    def _task(self, state, task_id):
        if task_id not in state["tasks"]:
            raise UadosError("Unknown task: " + task_id)
        return state["tasks"][task_id]

    def _owned(self, task, session):
        if task["status"] != "in_progress" or task.get("owner") != session["id"]:
            raise UadosError("Claim the task with this session before recording or completing work.")
        if datetime.fromisoformat(task["lease_until"]) <= datetime.now(timezone.utc):
            raise UadosError("Task lease expired; claim it again with a takeover reason.")

    def task_fingerprint(self, task, stage):
        policies = {p: text for p, text in maintained_context(self.root).items() if p.startswith(("ENGINEERING_RULES/", "MULTI_AGENT_SYSTEM/")) and p != "MULTI_AGENT_SYSTEM/role_plans.md"}
        spec = {key: task[key] for key in ("title", "description", "risk", "scope", "depends")}
        payload = {"spec": spec, "policies": policies, "files": scope_snapshot(self.root, task["scope"])}
        if task_version(task) >= 2:
            extra = maintained_context(self.root)
            from .storage import GENERATED_PATHS
            payload.update(plan=task.get("plan"), workflow_policies={p: t for p, t in extra.items() if (p.startswith((".agent/", "RESEARCH_MANAGEMENT/")) and p not in GENERATED_PATHS) or p == "CHANGE_REQUESTS/CHANGE_POLICY.md" or p == "MASTER_AGENT_WORKFLOW.md"})
            from .governance import checked
            checked(self, (task.get("plan") or {}).get("evidence", []))
            if task.get("change"):
                change = task.get("change_snapshot")
                if not change:
                    raise UadosError("Change request is unavailable.")
                checked(self, change["evidence"])
                payload["change"] = change
        if stage == "result":
            payload.update(revision=task["revision"], evidence=task["evidence"], work=task["work"])
            problems = check_evidence(self.root, task["evidence"])
            if problems:
                raise UadosError("; ".join(problems))
        return digest(payload)

    def _approval(self, state, task, stage):
        if task_version(task) >= 2:
            from .orchestration import require_consensus
            require_consensus(self, state, task, stage)
            if stage == "plan":
                from .governance import current_change
                if current_change(self, state, task)["status"] != "approved":
                    raise UadosError("Change request is not approved by plan consensus.")
        fingerprint = self.task_fingerprint(task, stage)
        latest = {}
        for review in task["reviews"]:
            if review["stage"] == stage and review["fingerprint"] == fingerprint:
                latest[review["agent"]] = review
        if any(r["verdict"] == "request_changes" for r in latest.values()):
            raise UadosError("Independent review requested changes; resolve or rework the proposal.")
        approved = [r for r in latest.values() if r["verdict"] == "approve" and r["agent"] not in task_contributors(task) and not check_evidence(self.root, r["evidence"])]
        if len(approved) < state["review_quorum"]:
            raise UadosError("Major task requires a current independent %s approval with unchanged review evidence." % stage)
        return fingerprint

    def add_task(self, session_id, title, description, risk="routine", scopes=(), depends=()):
        title, description = require_text(title, "Title"), require_text(description, "Description/acceptance criteria")
        if risk not in {"routine", "major"}:
            raise UadosError("Risk must be routine or major.")
        if risk == "major" and not scopes:
            raise UadosError("Major tasks need explicit implementation scope paths.")
        scope_snapshot(self.root, scopes)
        def operation(state, events, session):
            for dependency in depends:
                self._task(state, dependency)
            task_id = next_id(state, "T")
            state["tasks"][task_id] = {"id": task_id, "title": title, "description": description, "risk": risk, "scope": list(scopes), "depends": list(depends), "status": "pending", "author": session["agent"], "implementer": None, "contributors": [], "owner": None, "lease_until": None, "revision": 1, "work": [], "evidence": [], "reviews": [], "blocker": None, "submission_files": None}
            state["tasks"][task_id]["protocol_version"] = version(state)
            if state["phase"] == "maintenance":
                state["phase"] = "planning"
            return {"task": task_id, "status": "pending"}
        return self.mutate("task.add", title, operation, session_id)

    def claim_task(self, session_id, task_id, lease_minutes=60, takeover_reason=None):
        if lease_minutes <= 0 or lease_minutes > 10080:
            raise UadosError("Lease duration must be between 1 and 10080 minutes.")
        def operation(state, events, session):
            task = self._task(state, task_id)
            if task["status"] == "done":
                raise UadosError("Completed tasks cannot be claimed.")
            if task_version(task) >= 2:
                if not task.get("plan"):
                    raise UadosError("Protocol2 tasks require an implementation and validation plan before claim.")
                from .governance import checked
                checked(self, task["plan"]["evidence"])
                if task["risk"] == "major":
                    plan = state.get("role_plans", {}).get(task.get("role_plan"))
                    if plan:
                        implementers = {plan["assignments"].get(r["id"]) for r in plan["roles"] if not r["reviewer"] and r["capability"] in state.get("agents", {}).get(session["agent"], {}).get("capabilities", [])}
                        if session["agent"] not in implementers:
                            raise UadosError("Execution requires assignment to a selected nonreview implementation role with current capability; replan before changing implementers.")
            for dependency in task["depends"]:
                if self._task(state, dependency)["status"] != "done":
                    raise UadosError("Dependency is not complete: " + dependency)
            for other in state["tasks"].values():
                if other["id"] == task_id or not other.get("owner") or datetime.fromisoformat(other["lease_until"]) <= datetime.now(timezone.utc):
                    continue
                for proposed in task["scope"]:
                    for held in other["scope"]:
                        proposed_path = safe_path(self.root, proposed, allow_missing=True).resolve()
                        held_path = safe_path(self.root, held, allow_missing=True).resolve()
                        if proposed_path.is_relative_to(held_path) or held_path.is_relative_to(proposed_path):
                            raise UadosError("Scope overlaps an active task lease: %s (%s)" % (other["id"], held))
            if task.get("owner"):
                expired = datetime.fromisoformat(task["lease_until"]) <= datetime.now(timezone.utc)
                if not expired and task["owner"] != session_id:
                    raise UadosError("Task has an active lease owned by " + task["owner"])
                if expired:
                    reason = require_text(takeover_reason, "Expired lease takeover reason")
                    task["work"].append({"kind": "takeover", "summary": reason, "at": now(), "agent": session["agent"]})
            if task["risk"] == "major" and task["status"] != "in_progress":
                task["implementer"] = session["agent"]
                task["accepted_plan"] = self._approval(state, task, "plan")
                task["accepted_plan_reviewers"] = sorted({r["agent"] for r in task["reviews"] if r["stage"] == "plan" and r["verdict"] == "approve" and r["fingerprint"] == task["accepted_plan"]})
            elif task["risk"] == "major" and task.get("implementer") != session["agent"] and session["agent"] in task.get("accepted_plan_reviewers", []):
                raise UadosError("An accepted plan reviewer cannot take over its implementation. Close/replan the task and obtain a different independent reviewer.")
            task.update(status="in_progress", owner=session_id, implementer=session["agent"], lease_until=(datetime.now(timezone.utc) + timedelta(minutes=lease_minutes)).isoformat(), blocker=None)
            task["contributors"] = sorted(set(task.get("contributors", [])) | {session["agent"]})
            state["phase"] = "execution"
            return {"task": task_id, "owner": session_id, "lease_until": task["lease_until"]}
        return self.mutate("task.claim", "Claimed " + task_id, operation, session_id)

    def record_task(self, session_id, task_id, summary, evidence):
        summary = require_text(summary, "Work explanation")
        if not evidence:
            raise UadosError("A work submission requires validation evidence files.")
        def operation(state, events, session):
            task = self._task(state, task_id)
            self._owned(task, session)
            task["revision"] += 1
            task["evidence"] = evidence_files(self.root, evidence)
            task["submission_files"] = scope_snapshot(self.root, task["scope"])
            task["work"].append({"kind": "implementation", "summary": summary, "at": now(), "agent": session["agent"]})
            return {"task": task_id, "revision": task["revision"], "result_fingerprint": self.task_fingerprint(task, "result")}
        return self.mutate("task.record", summary, operation, session_id)

    def review_task(self, session_id, task_id, stage, verdict, challenge, evidence):
        challenge = require_text(challenge, "Adversarial challenge and findings")
        if stage not in {"plan", "result"} or verdict not in {"approve", "request_changes"}:
            raise UadosError("Invalid review stage or verdict.")
        if not evidence:
            raise UadosError("Independent review requires an evidence file.")
        def operation(state, events, session):
            task = self._task(state, task_id)
            if session["agent"] in task_contributors(task):
                raise UadosError("A different agent identity must independently review this task.")
            if stage == "plan" and task["status"] not in {"pending", "blocked"}:
                raise UadosError("Plan reviews occur before execution.")
            if stage == "result" and (task["status"] != "in_progress" or not task["evidence"]):
                raise UadosError("Result review requires submitted work on an active task.")
            if stage == "result" and scope_snapshot(self.root, task["scope"]) != task["submission_files"]:
                raise UadosError("Implementation changed after submission; record the work again.")
            review = {"agent": session["agent"], "session": session_id, "stage": stage, "verdict": verdict, "challenge": challenge, "at": now(), "fingerprint": self.task_fingerprint(task, stage), "evidence": evidence_files(self.root, evidence)}
            task["reviews"].append(review)
            return {"task": task_id, "review": review}
        return self.mutate("task.review", "%s review of %s: %s" % (stage, task_id, verdict), operation, session_id)

    def complete_task(self, session_id, task_id):
        def operation(state, events, session):
            task = self._task(state, task_id)
            self._owned(task, session)
            if not task["evidence"]:
                raise UadosError("Completion requires a explained work submission and validation evidence.")
            problems = check_evidence(self.root, task["evidence"])
            if problems:
                raise UadosError("; ".join(problems))
            if scope_snapshot(self.root, task["scope"]) != task["submission_files"]:
                raise UadosError("Implementation changed after submission; record and review the new result.")
            if task["risk"] == "major":
                self._approval(state, task, "result")
            task.update(status="done", owner=None, lease_until=None, completed_at=now(), completion_fingerprint=self.task_fingerprint(task, "result"))
            for decision in state["decisions"]:
                if decision.get("task") == task_id:
                    decision["status"] = "accepted"
            if task.get("change"):
                state["changes"][task["change"]]["status"] = "implemented"
            state["phase"] = "maintenance" if all(t["status"] == "done" for t in state["tasks"].values()) else "execution"
            return {"task": task_id, "status": "done"}
        return self.mutate("task.complete", "Completed " + task_id, operation, session_id)

    def block_task(self, session_id, task_id, reason):
        reason = require_text(reason, "Failed approach/blocker explanation")
        def operation(state, events, session):
            task = self._task(state, task_id)
            self._owned(task, session)
            task["work"].append({"kind": "failure", "summary": reason, "at": now(), "agent": session["agent"]})
            task.update(status="blocked", blocker=reason, owner=None, lease_until=None, revision=task["revision"] + 1)
            return {"task": task_id, "status": "blocked"}
        return self.mutate("task.block", reason, operation, session_id)

    def add_note(self, session_id, title, body, kind="technical"):
        title, body = require_text(title, "Title"), require_text(body, "Knowledge record")
        if kind not in {"technical", "lesson", "failure", "research"}:
            raise UadosError("Unknown knowledge category.")
        def operation(state, events, session):
            note_id = next_id(state, "N")
            state["notes"].append({"id": note_id, "title": title, "body": body, "kind": kind, "agent": session["agent"], "at": now()})
            return {"note": note_id}
        return self.mutate("note.add", title, operation, session_id)

    def add_decision(self, session_id, title, problem, alternatives, decision, reason, evidence, risk, task_id=None):
        for value, label in ((title, "Title"), (problem, "Problem"), (decision, "Decision"), (reason, "Rationale"), (risk, "Risk/revisit conditions")):
            require_text(value, label)
        if len(alternatives) < 2 or not evidence:
            raise UadosError("ADRs require at least two alternatives and evidence files.")
        for alternative in alternatives:
            require_text(alternative, "Alternative")
        def operation(state, events, session):
            task = self._task(state, task_id) if task_id else None
            if task:
                self._owned(task, session)
                if task["risk"] != "major":
                    raise UadosError("Link significant decisions to a major, independently reviewed task.")
                task["revision"] += 1
                task["submission_files"] = None
            decision_id = next_id(state, "ADR")
            state["decisions"].append({"id": decision_id, "title": title, "problem": problem, "alternatives": list(alternatives), "decision": decision, "reason": reason, "evidence": evidence_files(self.root, evidence), "risk": risk, "task": task_id, "status": "proposed" if task else "accepted", "agent": session["agent"], "at": now()})
            return {"decision": decision_id, "status": "proposed" if task else "accepted"}
        return self.mutate("decision.add", title, operation, session_id)

    def audit(self, repair=False):
        with project_lock(self.root), connect(self.root) as connection:
            state, events = load_ledger(connection)
            drift = projection_drift(self.root, state, events)
            repaired = list(drift) if repair else []
            if repair:
                write_projections(self.root, state, events)
                drift = projection_drift(self.root, state, events)
            errors = []
            try:
                context_bundle(self.root, state, events)
            except UadosError as exc:
                errors.append(str(exc))
            warnings = []
            for task in state["tasks"].values():
                errors.extend(check_evidence(self.root, task["evidence"]))
                if task["status"] == "done":
                    if not task["evidence"] or not task["work"]:
                        errors.append("Completed task lacks explained validation: " + task["id"])
                    if scope_snapshot(self.root, task["scope"]) != task["submission_files"]:
                        warnings.append("Completed task scope has changed since validation: " + task["id"])
                if task.get("owner") and datetime.fromisoformat(task["lease_until"]) <= datetime.now(timezone.utc):
                    warnings.append("Expired task lease: " + task["id"])
                current_review_fingerprints = {}
                for stage in ("plan", "result"):
                    try:
                        current_review_fingerprints[stage] = self.task_fingerprint(task, stage)
                    except UadosError:
                        current_review_fingerprints[stage] = None
                for review in task["reviews"]:
                    # Old challenged ballots remain visible in history. Only
                    # the current fingerprint participates in live audit; a
                    # renewed review is required before an old approval can be
                    # used after scope/policy/evidence changes.
                    if review.get("fingerprint") == current_review_fingerprints.get(review.get("stage")):
                        errors.extend(check_evidence(self.root, review["evidence"]))
            for adr in state["decisions"]:
                errors.extend(check_evidence(self.root, adr["evidence"]))
            for exp in state["experiments"].values():
                errors.extend(check_evidence(self.root, [exp["config"]] + exp["datasets"]))
                for run in exp["runs"]:
                    if run["status"] == "running":
                        warnings.append("Unresolved running experiment: %s / %s" % (exp["id"], run["id"]))
                    errors.extend(check_evidence(self.root, run.get("outputs", []) + run.get("analysis_evidence", [])))
            active_records = current_evidence(state)
            errors.extend(check_evidence(self.root, active_records))
            key = lambda record: (record["path"], record["sha256"], record.get("snapshot"))
            active_keys = {key(record) for record in active_records}
            history = {}
            for event in events:
                for record in all_evidence(event["state"]):
                    history.setdefault(key(record), record)
            historical_drift = []
            archived_originals = []
            for identifier, record in history.items():
                errors.extend(snapshot_problems(self.root, record))
                if identifier in active_keys:
                    continue
                changed = check_evidence(self.root, [record])
                if changed:
                    finding = {"path": record["path"], "sha256": record["sha256"], "snapshot": record.get("snapshot"), "problems": changed}
                    if record.get("snapshot") and not snapshot_problems(self.root, record):
                        archived_originals.append(finding)
                    else:
                        historical_drift.append(finding)
                        warnings.append("Unrecoverable historical evidence: %s (SHA-256 %s)" % (record["path"], record["sha256"]))
            result = {"ok": not errors and not drift, "event_count": len(events), "head_hash": events[-1]["hash"], "projection_drift": drift, "repaired": repaired, "errors": sorted(set(errors)), "warnings": sorted(set(warnings)), "protocol_version": version(state), "integrity_limit": "Local consistency check; the hash chain is not authenticated against a trusted external anchor."}
            result.update(history_ok=not historical_drift, historical_evidence_drift=historical_drift,
                          archived_originals=archived_originals, evidence_records_checked=len(history),
                          audit_scope="ok covers current bindings and all promised snapshots; history_ok separately covers legacy original-byte availability")
            if version(state) >= 2:
                from .governance import audit_candidates, idea_fingerprint
                for idea in state.get("ideas", {}).values():
                    for review in idea["reviews"]:
                        try:
                            if review["fingerprint"] != idea_fingerprint(self, state, idea):
                                result["warnings"].append("Stale novelty assessment: " + idea["id"])
                        except UadosError:
                            result["warnings"].append("Unavailable novelty evidence: " + idea["id"])
                result["improvement_candidates"] = audit_candidates(result)
            return result

    def export(self, destination, include=()):
        destination = Path(destination).resolve()
        if destination.exists() or destination.is_relative_to(self.root):
            raise UadosError("Export destination must be a new directory outside the project.")
        with project_lock(self.root), connect(self.root) as connection:
            state, events = load_ledger(connection)
            if projection_drift(self.root, state, events):
                raise UadosError("Repair generated views before exporting.")
            files = set(projection_map(state, events)) | set(maintained_context(self.root))
            unavailable_scopes = set()
            def include_recorded_scope(scopes):
                snapshot = scope_snapshot(self.root, scopes)
                unavailable_scopes.update(path for path, value in snapshot.items() if value == "missing")
                files.update(path for path, value in snapshot.items() if value != "missing")
            for directory in REQUIRED_DIRECTORIES:
                files.update(p.relative_to(self.root).as_posix() for p in safe_path(self.root, directory).rglob("*.md"))
            for task in state["tasks"].values():
                include_recorded_scope(task["scope"])
                files.update(r["path"] for r in task["evidence"])
            for adr in state["decisions"]:
                files.update(r["path"] for r in adr["evidence"])
            active_records = current_evidence(state)
            files.update(r["path"] for r in active_records)
            historical_records = { (record["path"], record["sha256"], record.get("snapshot")): record
                for event in events for record in all_evidence(event["state"]) }
            unavailable_history = []
            for record in historical_records.values():
                problems = snapshot_problems(self.root, record)
                if problems:
                    raise UadosError("; ".join(problems))
                if record.get("snapshot"):
                    files.add(record["snapshot"])
                path = safe_path(self.root, record["path"], allow_missing=True)
                if path.is_file():
                    files.add(record["path"])
                if check_evidence(self.root, [record]) and not record.get("snapshot"):
                    unavailable_history.append({"path": record["path"], "sha256": record["sha256"]})
            for exp in state["experiments"].values():
                include_recorded_scope(exp["scope"])
                files.update(r["path"] for r in [exp["config"]] + exp["datasets"])
                for run in exp["runs"]:
                    files.update(r["path"] for r in run.get("outputs", []) + run.get("analysis_evidence", []))
            files.update(scope_snapshot(self.root, include))
            sources = {relative: safe_path(self.root, relative) for relative in files}
            if any(not p.is_file() for p in sources.values()):
                raise UadosError("Export includes an unavailable file; restore it or select a valid scope.")
            destination.mkdir(parents=True)
            for directory in REQUIRED_DIRECTORIES:
                (destination / directory).mkdir(exist_ok=True)
            (destination / ".uados").mkdir()
            with connect(destination) as backup:
                connection.backup(backup)
            for relative, source in sources.items():
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            return {"destination": str(destination), "file_count": len(files), "event_count": len(events), "unavailable_scopes": sorted(unavailable_scopes), "unrecoverable_historical_evidence": unavailable_history, "note": "Available scopes, current evidence, historical snapshots and context copied. Missing legacy originals are disclosed, never invented. Use --include for other dependencies; inspect for private data before sharing."}

    def upgrade(self, session_id, task_id):
        def operation(state, events, session):
            task = self._task(state, task_id)
            self._owned(task, session)
            if task["risk"] != "major":
                raise UadosError("A workflow upgrade requires an owned major task with prior independent plan approval.")
            if version(state) >= 2:
                raise UadosError("Project already uses protocol2; historical tasks retain their recorded protocol.")
            from .protocol import PROTOCOL_FILES
            missing = [p for p in PROTOCOL_FILES if not safe_path(self.root, p, allow_missing=True).is_file()]
            if missing:
                raise UadosError("Install maintained Phase2 scaffold policies before upgrade: " + ", ".join(missing))
            for old_task in state["tasks"].values():
                old_task.setdefault("protocol_version", 1)
            extend_state(state)
            state["protocol_version"] = 2
            return {"protocol_version": 2, "history_preserved": True, "legacy_tasks": len(state["tasks"])}
        return self.mutate("project.upgrade", "Enabled workflow protocol2 with preserved legacy tasks", operation, session_id)
