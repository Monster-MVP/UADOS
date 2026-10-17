"""Independent mechanical review for archived evidence and honest historical drift."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

repository = Path(sys.argv[1])
sys.path.insert(0, str(repository / "src"))
from uados.project import Project, check_evidence
from uados.storage import UadosError, evidence_files, snapshot_problems
from uados import governance as gov


def current(project, session):
    issued = project.refresh_session(session)
    assert issued["report"]["title"] == "PROJECT UNDERSTANDING REPORT"
    project.acknowledge(session, issued["report_hash"])


def start(project, label):
    issued = project.start_session(label)
    project.acknowledge(issued["session"], issued["report_hash"])
    return issued["session"]


def reject(function):
    try:
        function()
    except UadosError as error:
        return {"passed": True, "error": str(error)}
    return {"passed": False, "finding": "Operation unexpectedly succeeded"}


def archive_versions_and_recovery():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "project"
        project = Project.initialize(root, "Snapshot probe", "Preserve originals honestly")
        author = start(project, "Fixture author")
        path = root / "evidence.txt"
        path.write_bytes(b"Original evidence version 1\n")
        project.add_decision(author, "Original rationale", "Need durable rationale", ["Loose docs", "Recorded artifact"], "Recorded artifact", "Keep exact bytes", ["evidence.txt"], "Trusted local proof only")
        first = project.read()[0]["decisions"][0]["evidence"][0]
        path.write_bytes(b"Updated evidence version 2\n")
        current(project, author)
        project.add_decision(author, "Updated rationale", "Need current rationale", ["Keep first", "Version it"], "Version it", "Preserve both", ["evidence.txt"], "Current bytes changed")
        second = project.read()[0]["decisions"][1]["evidence"][0]
        both = (root / first["snapshot"]).read_bytes() == b"Original evidence version 1\n" and (root / second["snapshot"]).read_bytes() == b"Updated evidence version 2\n"
        active_drift = reject(lambda: project.add_decision(author, "Current drift", "P", ["A", "B"], "D", "R", ["evidence.txt"], "R"))
        audit = project.audit()
        destination = Path(directory) / "exported"
        exported = project.export(destination)
        records = [first, second]
        copies_present = all((destination / record["snapshot"]).is_file() for record in records)
        (destination / ".uados/ledger.sqlite3").unlink()
        Project.rebuild_ledger(destination)
        rebuild_preserved = all((destination / record["snapshot"]).read_bytes() == (root / record["snapshot"]).read_bytes() for record in records)
        return {"passed": both and copies_present and rebuild_preserved, "snapshots_distinct": first["snapshot"] != second["snapshot"], "audit_current_errors": audit["errors"], "copies_present": copies_present, "rebuild_preserved": rebuild_preserved, "export": exported}


def current_gate_rejects_live_edit():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "project"
        project = Project.initialize(root, "Current approval probe", "Snapshots never approve changed current evidence")
        author = start(project, "Fixture author")
        (root / "plan.txt").write_bytes(b"Plan v1\n")
        (root / "proof.txt").write_bytes(b"Proof v1\n")
        task = project.add_task(author, "Routine task", "Check current evidence", scopes=["code.py"])["task"]
        gov.plan_task(project, author, task, "Implement bounded change", "Validate bytes", ["plan.txt"])
        project.claim_task(author, task)
        (root / "code.py").write_bytes(b"VALUE = 1\n")
        project.record_task(author, task, "Validated current bytes", ["proof.txt"])
        record = project.read()[0]["tasks"][task]["evidence"][0]
        (root / "proof.txt").write_bytes(b"Changed current proof\n")
        result = reject(lambda: project.complete_task(author, task))
        result["snapshot_still_valid"] = not snapshot_problems(root, record)
        result["passed"] = result["passed"] and result["snapshot_still_valid"]
        return result


def existing_corrupt_snapshot_is_rejected():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "project"
        Project.initialize(root, "Corrupt snapshot probe", "Reject corruption")
        (root / "evidence.txt").write_bytes(b"Evidence\n")
        record = evidence_files(root, ["evidence.txt"])[0]
        target = root / record["snapshot"]
        target.write_bytes(b"Corrupt replacement\n")
        result = reject(lambda: evidence_files(root, ["evidence.txt"]))
        result["corruption_preserved_for_diagnosis"] = target.read_bytes() == b"Corrupt replacement\n"
        result["passed"] = result["passed"] and result["corruption_preserved_for_diagnosis"]
        return result


def historical_snapshot_missing_is_error():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "project"
        project = Project.initialize(root, "Historical corruption probe", "Detect historical corruption")
        author = start(project, "Fixture author")
        (root / "plan.txt").write_text("Initial design\n")
        task = project.add_task(author, "Major task", "Preserve superseded plans", "major", ["code.py"])["task"]
        gov.plan_task(project, author, task, "Old plan", "Old validation", ["plan.txt"])
        old = project.read()[0]["tasks"][task]["plan"]["evidence"][0]
        gov.replan_task(project, author, task, "Explicitly supersede old design")
        (root / "plan.txt").write_text("Current design\n")
        gov.plan_task(project, author, task, "Current plan", "Current validation", ["plan.txt"])
        good = project.audit()
        (root / old["snapshot"]).unlink()
        bad = project.audit()
        return {"passed": good["ok"] and good["history_ok"] and bool(good["archived_originals"]) and not bad["ok"] and any("snapshot unavailable" in error.lower() for error in bad["errors"]), "preserved_originals": len(good["archived_originals"]), "errors_after_delete": bad["errors"]}


def legacy_lost_original_warns_honestly():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "project"
        project = Project.initialize(root, "Legacy loss probe", "Never invent old evidence", protocol_version=1)
        author = start(project, "Fixture author")
        (root / "plan.txt").write_text("Legacy design\n")
        task = project.add_task(author, "Major task", "Historical plan", "major", ["code.py"])["task"]
        original = evidence_files(root, ["plan.txt"])[0]
        legacy = {key: original[key] for key in ("path", "sha256", "bytes")}
        with patch("uados.governance.evidence_files", return_value=[legacy]):
            gov.plan_task(project, author, task, "Old plan", "Old validation", ["plan.txt"])
        gov.replan_task(project, author, task, "Explicitly supersede prior legacy record")
        (root / "plan.txt").write_text("Current design\n")
        gov.plan_task(project, author, task, "Current plan", "Current validation", ["plan.txt"])
        (root / original["snapshot"]).unlink()
        audit = project.audit()
        destination = Path(directory) / "exported"
        exported = project.export(destination)
        return {"passed": audit["ok"] and not audit["history_ok"] and bool(audit["historical_evidence_drift"]) and bool(exported["unrecoverable_historical_evidence"]), "history_ok": audit["history_ok"], "warnings": audit["warnings"], "export_disclosure": exported["unrecoverable_historical_evidence"]}


results = {}
for name, function in (("archive_versions_and_recovery", archive_versions_and_recovery), ("current_gate_rejects_live_edit", current_gate_rejects_live_edit), ("existing_corrupt_snapshot_is_rejected", existing_corrupt_snapshot_is_rejected), ("historical_snapshot_missing_is_error", historical_snapshot_missing_is_error), ("legacy_lost_original_warns_honestly", legacy_lost_original_warns_honestly)):
    try:
        results[name] = function()
    except Exception as error:
        results[name] = {"passed": False, "exception": type(error).__name__, "message": str(error)}
print(json.dumps({"independent_mechanical_fixture": True, "results": results}, indent=2, sort_keys=True))
sys.exit(0 if all(value["passed"] for value in results.values()) else 1)
