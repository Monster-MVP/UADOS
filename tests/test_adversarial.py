"""Adversarial integration checks for persisted workflow contracts and recovery."""

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock


SOURCE = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SOURCE))

from uados.project import Project
from uados.research import (add_experiment, conclude_experiment,
                            resolve_experiment, run_experiment)
from uados.storage import UadosError


class AdversarialWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "project"
        self.root.mkdir()
        (self.root / "src").mkdir()
        (self.root / "src" / "model.py").write_text("VALUE = 1\n", encoding="utf-8")
        (self.root / "validation.txt").write_text("Validated under the stated conditions.\n", encoding="utf-8")
        (self.root / "plan-review.txt").write_text("Challenged scope, assumptions and alternatives.\n", encoding="utf-8")
        (self.root / "result-review.txt").write_text("Inspected code and validation evidence.\n", encoding="utf-8")
        (self.root / "config.json").write_text('{"seed": 7}\n', encoding="utf-8")
        self.project = Project.initialize(self.root, "Adversarial project", "Preserve accountable project knowledge", protocol_version=1)

    def session(self, identity: str) -> str:
        started = self.project.start_session(identity)
        self.project.acknowledge(started["session"], started["report_hash"])
        return str(started["session"])

    def refresh(self, session):
        result = self.project.refresh_session(session)
        self.project.acknowledge(session, result["report_hash"])

    def major_task(self, scope=("src",)):
        author = self.session("Author")
        task = self.project.add_task(author, "Replace implementation", "Acceptance: validation passes; review challenges assumptions", "major", scope)["task"]
        reviewer = self.session("Reviewer")
        self.project.review_task(reviewer, task, "plan", "approve", "Examined the implementation boundary and rejected unnecessary dependencies", ["plan-review.txt"])
        return author, reviewer, task

    def submit_major(self):
        author, reviewer, task = self.major_task()
        self.refresh(author)
        self.project.claim_task(author, task)
        (self.root / "src" / "model.py").write_text("VALUE = 2\n", encoding="utf-8")
        self.project.record_task(author, task, "Implemented and validated replacement", ["validation.txt"])
        self.refresh(reviewer)
        self.project.review_task(reviewer, task, "result", "approve", "Checked boundary behavior and validation assumptions", ["result-review.txt"])
        self.refresh(author)
        return author, reviewer, task

    def experiment(self, script):
        (self.root / "src" / "experiment.py").write_text(script, encoding="utf-8")
        session = self.session("Researcher")
        experiment = add_experiment(self.project, session, "Controlled run", "Measure the command outcome and retain uncertainty", [sys.executable, "src/experiment.py"], "config.json", [], 7, ["src"])["experiment"]
        return session, experiment

    def test_acknowledgment_is_required_and_forged_report_rejected(self):
        start = self.project.start_session("Uninitialized agent")
        count = len(self.project.read()[1])
        with self.assertRaises(UadosError):
            self.project.add_note(start["session"], "Premature change", "This must not be committed")
        with self.assertRaises(UadosError):
            self.project.acknowledge(start["session"], "0" * 64)
        state, events, drift = self.project.read()
        self.assertEqual(count, len(events))
        self.assertFalse(state["sessions"][start["session"]]["acknowledged"])
        self.assertFalse(drift)

    def test_other_session_changes_force_new_context_acknowledgment(self):
        first, second = self.session("Agent A"), self.session("Agent B")
        self.project.add_note(first, "New decision context", "Agent B must read this before acting")
        with self.assertRaisesRegex(UadosError, "context changed"):
            self.project.add_note(second, "Stale context", "This must not be committed")
        report = self.project.refresh_session(second)
        with self.assertRaisesRegex(UadosError, "acknowledge"):
            self.project.add_note(second, "Unread refresh", "This must not be committed")
        self.project.acknowledge(second, report["report_hash"])
        self.project.add_note(second, "Acknowledged context", "Continued after reading the updated report")
        self.assertEqual(2, len(self.project.read()[0]["notes"]))

    def test_maintained_rules_change_invalidates_session(self):
        session = self.session("Agent")
        rules = self.root / "ENGINEERING_RULES" / "extra.md"
        rules.write_text("All changes require boundary validation.\n", encoding="utf-8")
        with self.assertRaisesRegex(UadosError, "context changed"):
            self.project.add_note(session, "Stale rules", "Must read new engineering rules first")
        self.refresh(session)
        self.project.add_note(session, "New rules read", "Boundary validation is now understood")

    def test_concurrent_processes_preserve_all_session_events(self):
        script = "import json, sys; from uados.project import Project; print(json.dumps(Project(sys.argv[1]).start_session(sys.argv[2])))"
        environment = dict(os.environ, PYTHONPATH=str(SOURCE))
        processes = [subprocess.Popen([sys.executable, "-c", script, str(self.root), "Worker %d" % index], env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for index in range(4)]
        try:
            results = []
            for process in processes:
                stdout, stderr = process.communicate(timeout=20)
                self.assertEqual(0, process.returncode, stderr)
                results.append(json.loads(stdout))
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                process.communicate()
        state, events, drift = self.project.read()
        self.assertEqual(4, len({result["session"] for result in results}))
        self.assertEqual(4, len(state["sessions"]))
        self.assertEqual(list(range(1, 6)), [event["sequence"] for event in events])
        self.assertFalse(drift)

    def test_concurrent_claims_cannot_overwrite_task_ownership(self):
        first = self.session("First claimant")
        task = str(self.project.add_task(first, "Exclusive task", "Only one cooperative owner", scopes=["src"])["task"])
        second = self.session("Second claimant")
        script = "import json, sys; from uados.project import Project; from uados.storage import UadosError; p=Project(sys.argv[1]);\ntry:\n print(json.dumps(p.claim_task(sys.argv[2], sys.argv[3])))\nexcept UadosError as error:\n print(json.dumps({'error':str(error)}))\n sys.exit(2)"
        environment = dict(os.environ, PYTHONPATH=str(SOURCE))
        processes = [subprocess.Popen([sys.executable, "-c", script, str(self.root), session, task], env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for session in (first, second)]
        try:
            results = []
            for process in processes:
                stdout, stderr = process.communicate(timeout=20)
                self.assertIn(process.returncode, (0, 2), stderr)
                results.append((process.returncode, json.loads(stdout)))
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                process.communicate()
        successes = [result for code, result in results if code == 0]
        self.assertEqual(1, len(successes))
        state, events, drift = self.project.read()
        self.assertEqual(successes[0]["owner"], state["tasks"][task]["owner"])
        self.assertEqual(1, sum(event["kind"] == "task.claim" for event in events))
        self.assertFalse(drift)

    def test_plan_approval_becomes_stale_when_scoped_code_changes(self):
        author, _, task = self.major_task()
        self.refresh(author)
        (self.root / "src" / "model.py").write_text("VALUE = 99\n", encoding="utf-8")
        with self.assertRaisesRegex(UadosError, "plan approval"):
            self.project.claim_task(author, task)
        self.assertEqual("pending", self.project.read()[0]["tasks"][task]["status"])

    def test_plan_reviewer_cannot_supply_own_pre_execution_approval(self):
        _, reviewer, task = self.major_task()
        with self.assertRaisesRegex(UadosError, "independent.*plan approval"):
            self.project.claim_task(reviewer, task)
        self.assertIsNone(self.project.read()[0]["tasks"][task]["implementer"])

    def test_expired_lease_takeover_cannot_turn_reviewer_into_implementer(self):
        author, reviewer, task = self.major_task()
        self.refresh(author)
        self.project.claim_task(author, task)
        self.refresh(reviewer)
        future = datetime.now(timezone.utc) + timedelta(hours=2)
        with mock.patch("uados.project.datetime", wraps=datetime) as clock:
            clock.now.return_value = future
            with self.assertRaisesRegex(UadosError, "independent|review"):
                self.project.claim_task(reviewer, task, takeover_reason="Recovering the expired owner")
        self.assertEqual(author, self.project.read()[0]["tasks"][task]["owner"])

    def test_previous_implementer_cannot_review_inherited_implementation(self):
        _, plan_reviewer, task = self.major_task()
        first = self.session("First implementer")
        self.project.claim_task(first, task)
        (self.root / "src" / "model.py").write_text("VALUE = 10\n", encoding="utf-8")
        self.project.record_task(first, task, "Authored the implementation", ["validation.txt"])
        self.project.close_session(first, "Implementation handed over", ["Revalidate inherited code"])
        self.refresh(plan_reviewer)
        self.project.review_task(plan_reviewer, task, "plan", "approve", "Challenged the resumed scope and inherited assumptions", ["plan-review.txt"])
        successor = self.session("Successor implementer")
        self.project.claim_task(successor, task)
        self.project.record_task(successor, task, "Revalidated inherited implementation without rewriting it", ["validation.txt"])
        returning_contributor = self.session("First implementer")
        with self.assertRaisesRegex(UadosError, "independent|contribut|different agent"):
            self.project.review_task(returning_contributor, task, "result", "approve", "This would be review of my own prior implementation", ["result-review.txt"])

    def test_review_evidence_change_invalidates_plan_approval(self):
        author, _, task = self.major_task()
        self.refresh(author)
        (self.root / "plan-review.txt").write_text("Review evidence replaced after approval\n", encoding="utf-8")
        with self.assertRaisesRegex(UadosError, "unchanged review evidence"):
            self.project.claim_task(author, task)

    def test_result_approval_cannot_cover_new_untracked_scoped_file(self):
        author, _, task = self.submit_major()
        (self.root / "src" / "unreviewed.py").write_text("UNREVIEWED = True\n", encoding="utf-8")
        with self.assertRaisesRegex(UadosError, "Implementation changed"):
            self.project.complete_task(author, task)
        self.assertEqual("in_progress", self.project.read()[0]["tasks"][task]["status"])

    def test_same_identity_in_another_session_is_not_independent(self):
        author = self.session("Same agent")
        task = self.project.add_task(author, "Major work", "Independent challenge required", "major", ["src"])["task"]
        duplicate = self.session("Same agent")
        with self.assertRaisesRegex(UadosError, "different agent identity"):
            self.project.review_task(duplicate, task, "plan", "approve", "This identity is still the author", ["plan-review.txt"])

    def test_root_scope_does_not_make_plan_approval_self_invalidating(self):
        author, _, task = self.major_task(scope=(".",))
        self.refresh(author)
        self.project.claim_task(author, task)
        self.assertEqual(author, self.project.read()[0]["tasks"][task]["owner"])

    def test_non_utf8_generated_projection_is_repairable(self):
        (self.root / ".uados" / "state.json").write_bytes(b"\xff\xfe corrupted export")
        result = self.project.audit(repair=True)
        self.assertTrue(result["ok"], result)
        self.assertIn(".uados/state.json", result["repaired"])
        self.assertEqual("Adversarial project", json.loads((self.root / ".uados" / "state.json").read_text(encoding="utf-8"))["name"])

    def test_event_corruption_is_rejected_without_rewriting_history(self):
        database = self.root / ".uados" / "ledger.sqlite3"
        with sqlite3.connect(str(database)) as connection:
            event = json.loads(connection.execute("SELECT value FROM events WHERE sequence=1").fetchone()[0])
            event["summary"] = "Changed without updating the event hash"
            connection.execute("UPDATE events SET value=? WHERE sequence=1", (json.dumps(event),))
        before = database.read_bytes()
        with self.assertRaisesRegex(UadosError, "chain.*inconsistent"):
            self.project.audit(repair=True)
        self.assertEqual(before, database.read_bytes())

    def test_uncommitted_state_substitution_is_rejected(self):
        database = self.root / ".uados" / "ledger.sqlite3"
        with sqlite3.connect(str(database)) as connection:
            state = json.loads(connection.execute("SELECT value FROM state WHERE id=1").fetchone()[0])
            state["objective"] = "Substituted state without a committed event"
            connection.execute("UPDATE state SET value=? WHERE id=1", (json.dumps(state),))
        with self.assertRaisesRegex(UadosError, "state disagrees"):
            self.project.read()

    def test_valid_json_with_invalid_ledger_structure_is_reported_cleanly(self):
        database = self.root / ".uados" / "ledger.sqlite3"
        with sqlite3.connect(str(database)) as connection:
            original_state = connection.execute("SELECT value FROM state WHERE id=1").fetchone()[0]
            original_event = connection.execute("SELECT value FROM events WHERE sequence=1").fetchone()[0]
        for table, key, value in (("state", "id", "[]"), ("events", "sequence", "null")):
            with self.subTest(table=table):
                try:
                    with sqlite3.connect(str(database)) as connection:
                        connection.execute("UPDATE %s SET value=? WHERE %s=1" % (table, key), (value,))
                    with self.assertRaises(UadosError):
                        self.project.audit(repair=True)
                finally:
                    with sqlite3.connect(str(database)) as connection:
                        connection.execute("UPDATE state SET value=? WHERE id=1", (original_state,))
                        connection.execute("UPDATE events SET value=? WHERE sequence=1", (original_event,))

    def test_rebuild_refuses_truncated_journal_without_leaving_database(self):
        ledger = self.root / ".uados" / "ledger.sqlite3"
        ledger.unlink()
        journal = self.root / ".uados" / "events.jsonl"
        original = journal.read_text(encoding="utf-8")
        journal.write_text(original + '{"sequence":2', encoding="utf-8")
        with self.assertRaises(UadosError):
            Project.rebuild_ledger(self.root)
        self.assertFalse(ledger.exists())
        self.assertFalse(list((self.root / ".uados").glob(".rebuild-*")))
        self.assertEqual(original + '{"sequence":2', journal.read_text(encoding="utf-8"))

    def test_rebuild_refuses_valid_json_with_broken_chain(self):
        ledger = self.root / ".uados" / "ledger.sqlite3"
        ledger.unlink()
        journal = self.root / ".uados" / "events.jsonl"
        event = json.loads(journal.read_text(encoding="utf-8"))
        event["summary"] = "Substituted exported event"
        journal.write_text(json.dumps(event) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(UadosError, "chain.*inconsistent"):
            Project.rebuild_ledger(self.root)
        self.assertFalse(ledger.exists())
        self.assertFalse(list((self.root / ".uados").glob(".rebuild-*")))

    def test_rebuild_refuses_disagreement_between_exported_state_and_events(self):
        ledger = self.root / ".uados" / "ledger.sqlite3"
        ledger.unlink()
        state_export = self.root / ".uados" / "state.json"
        state = json.loads(state_export.read_text(encoding="utf-8"))
        state["objective"] = "A different project state"
        state_export.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaisesRegex(UadosError, "state and event history disagree"):
            Project.rebuild_ledger(self.root)
        self.assertFalse(ledger.exists())

    def test_rebuild_restores_missing_state_export_from_complete_history(self):
        session = self.session("Original researcher")
        self.project.add_note(session, "Rejected approach", "The alternative failed its acceptance condition", "failure")
        self.project.close_session(session, "Preserved reasoning for a successor", ["Challenge the revised approach"], failed=["Initial approach failed"])
        before_state, before_events, _ = self.project.read()
        (self.root / ".uados" / "ledger.sqlite3").unlink()
        (self.root / ".uados" / "state.json").unlink()
        Project.rebuild_ledger(self.root)
        restored = Project(self.root)
        state, events, drift = restored.read()
        self.assertEqual(before_state, state)
        self.assertEqual(before_events, events)
        self.assertFalse(drift)
        successor = restored.start_session("Successor")
        self.assertTrue(successor["report"]["failed_approaches"])
        self.assertEqual(["Challenge the revised approach"], successor["report"]["latest_handover"]["next"])

    def test_parent_traversal_and_absolute_scope_are_rejected(self):
        author = self.session("Agent")
        count = len(self.project.read()[1])
        for scope in ("../outside", str(Path(self.temporary.name) / "outside")):
            with self.subTest(scope=scope), self.assertRaises(UadosError):
                self.project.add_task(author, "Invalid scope", "Must remain in project", scopes=[scope])
        self.assertEqual(count, len(self.project.read()[1]))

    @unittest.skipUnless(hasattr(os, "symlink"), "Symlinks are unavailable")
    def test_symlink_evidence_is_rejected_before_commit(self):
        author = self.session("Agent")
        task = self.project.add_task(author, "Scoped work", "Evidence remains local", scopes=["src"])["task"]
        self.project.claim_task(author, task)
        outside = Path(self.temporary.name) / "outside.txt"
        outside.write_text("Private external evidence", encoding="utf-8")
        (self.root / "escaped.txt").symlink_to(outside)
        count = len(self.project.read()[1])
        with self.assertRaisesRegex(UadosError, "Symlinks"):
            self.project.record_task(author, task, "Attempted external evidence", ["escaped.txt"])
        self.assertEqual(count, len(self.project.read()[1]))

    @unittest.skipUnless(hasattr(os, "symlink"), "Symlinks are unavailable")
    def test_generated_directory_symlink_cannot_receive_repair_writes(self):
        original = self.root / "PROJECT_MEMORY"
        backup = self.root / "saved-memory"
        original.rename(backup)
        external = Path(self.temporary.name) / "external-memory"
        external.mkdir()
        sentinel = external / "knowledge.md"
        sentinel.write_text("External data must remain unchanged", encoding="utf-8")
        original.symlink_to(external, target_is_directory=True)
        with self.assertRaisesRegex(UadosError, "Symlinks"):
            self.project.audit(repair=True)
        self.assertEqual("External data must remain unchanged", sentinel.read_text(encoding="utf-8"))

    def test_timeout_is_durable_and_captured_output_is_auditable(self):
        session, experiment = self.experiment("import time\nprint('started', flush=True)\ntime.sleep(5)\n")
        result = run_experiment(self.project, session, experiment, timeout=0.05)
        self.assertEqual("timed_out", result["status"])
        state, events, drift = self.project.read()
        run = state["experiments"][experiment]["runs"][0]
        self.assertIsNotNone(run["returncode"])
        self.assertEqual(2, len(run["outputs"]))
        self.assertEqual(["experiment.start", "experiment.finish"], [event["kind"] for event in events if event["kind"].startswith("experiment.") and event["kind"] != "experiment.add"])
        self.assertFalse(drift)
        self.assertTrue(self.project.audit()["ok"])

    def test_launcher_crash_preserves_intent_and_requires_explicit_recovery(self):
        session, experiment = self.experiment("print('recovered execution')\n")
        real_popen = subprocess.Popen

        def crash_experiment_launch(command, *args, **kwargs):
            if command[0] == sys.executable:
                raise RuntimeError("simulated launcher crash")
            return real_popen(command, *args, **kwargs)

        with mock.patch("uados.research.subprocess.Popen", side_effect=crash_experiment_launch):
            with self.assertRaisesRegex(RuntimeError, "simulated launcher crash"):
                run_experiment(self.project, session, experiment)
        state, _, drift = Project(self.root).read()
        self.assertEqual("running", state["experiments"][experiment]["runs"][0]["status"])
        self.assertFalse(drift)
        self.assertTrue(any("Unresolved running experiment" in warning for warning in self.project.audit()["warnings"]))
        with self.assertRaisesRegex(UadosError, "unresolved run"):
            run_experiment(self.project, session, experiment)
        successor = self.session("Successor researcher")
        result = resolve_experiment(self.project, successor, experiment, "Launcher failure confirmed; no child process was created")
        self.assertEqual("interrupted", result["status"])
        retry = run_experiment(self.project, successor, experiment)
        self.assertEqual("succeeded", retry["status"])
        self.assertEqual(2, len(self.project.read()[0]["experiments"][experiment]["runs"]))

    def test_missing_executable_is_a_failed_run_with_preserved_diagnostics(self):
        session, experiment = self.experiment("print('unused')\n")
        missing = str(Path(self.temporary.name) / "nonexistent-command")
        second = add_experiment(self.project, session, "Unavailable runtime", "Failure must remain recorded", [missing], "config.json", [], 7, ["src"])["experiment"]
        result = run_experiment(self.project, session, second)
        self.assertEqual("failed", result["status"])
        self.assertIsNone(result["returncode"])
        self.assertTrue(result["error"])
        self.assertTrue(self.project.audit()["ok"])

    def test_exit_zero_with_changed_code_is_invalidated(self):
        session, experiment = self.experiment("from pathlib import Path\nPath('src/model.py').write_text('VALUE = 3\\n')\nprint('changed own implementation')\n")
        result = run_experiment(self.project, session, experiment)
        self.assertEqual(0, result["returncode"])
        self.assertEqual("invalidated", result["status"])
        run = self.project.read()[0]["experiments"][experiment]["runs"][0]
        self.assertTrue(run["code_changed_during_run"])
        self.assertEqual(2, len(run["outputs"]))

    def test_analysis_evidence_is_audited_and_transferred(self):
        session, experiment = self.experiment("print('measurement=1')\n")
        run_experiment(self.project, session, experiment)
        self.refresh(session)
        analysis = self.root / "analysis.txt"
        analysis.write_text("Interpretation: one controlled observation; generalization uncertain.\n", encoding="utf-8")
        conclude_experiment(self.project, session, experiment, "The command produced the expected observation; no broader claim is justified", ["analysis.txt"])
        destination = Path(self.temporary.name) / "transferred-project"
        self.project.export(destination)
        self.assertTrue((destination / "analysis.txt").is_file())
        self.assertTrue(Project(destination).audit()["ok"])
        analysis.write_text("Analysis changed without review\n", encoding="utf-8")
        audit = self.project.audit()
        self.assertFalse(audit["ok"])
        self.assertTrue(any("analysis.txt" in error for error in audit["errors"]))


if __name__ == "__main__":
    unittest.main()
