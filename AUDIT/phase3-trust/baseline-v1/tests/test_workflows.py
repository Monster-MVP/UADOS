import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from uados.context import REQUIRED_DIRECTORIES, context_bundle
from uados.project import Project
from uados.research import add_experiment, conclude_experiment, run_experiment
from uados.storage import UadosError


class Workflows(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "project"
        self.project = Project.initialize(self.root, "Test project", "Preserve work across agent changes", protocol_version=1)
        self.session = self.start("Agent-A")

    def tearDown(self):
        self.temporary.cleanup()

    def start(self, agent):
        result = self.project.start_session(agent)
        self.project.acknowledge(result["session"], result["report_hash"])
        return result["session"]

    def refresh(self, session):
        result = self.project.refresh_session(session)
        self.project.acknowledge(session, result["report_hash"])

    def write(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return path

    def task(self, title="Implement", risk="routine", depends=()):
        return self.project.add_task(self.session, title, "Acceptance: validation evidence and an explained result", risk, ["code.py"], depends)["task"]

    def test_init_modes_and_non_overwrite(self):
        for directory in REQUIRED_DIRECTORIES:
            self.assertTrue((self.root / directory).is_dir())
        with self.assertRaisesRegex(UadosError, "already exists"):
            Project.initialize(self.root, "other", "other")
        mode_root = Path(self.temporary.name) / "hybrid"
        mode_root.mkdir()
        (mode_root / "analysis.ipynb").write_text("{}")
        (mode_root / "app.py").write_text("pass")
        project = Project.initialize(mode_root, "Hybrid", "Run research and engineering")
        state, _, _ = project.read()
        self.assertEqual(state["mode"], "hybrid")
        self.assertEqual(state["mode_detection"]["confidence"], "heuristic")
        self.assertEqual(self.project.read()[0]["mode"], "software")

    def test_understanding_gate_and_changed_policies(self):
        session = self.project.start_session("New-Agent")
        with self.assertRaisesRegex(UadosError, "acknowledge"):
            self.project.add_note(session["session"], "Too soon", "No report read")
        with self.assertRaisesRegex(UadosError, "hash"):
            self.project.acknowledge(session["session"], "wrong")
        self.project.acknowledge(session["session"], session["report_hash"])
        self.write("ENGINEERING_RULES/new-policy.md", "All tasks need acceptance evidence.")
        with self.assertRaisesRegex(UadosError, "context changed"):
            self.project.add_note(session["session"], "stale", "must refresh")
        self.refresh(session["session"])
        self.project.add_note(session["session"], "Policy", "Read the new rule")

    def test_adopt_preserves_existing_project_documentation(self):
        root = Path(self.temporary.name) / "existing"
        root.mkdir()
        (root / "README.md").write_text("Existing application architecture and usage")
        (root / "app.py").write_text("pass")
        with self.assertRaisesRegex(UadosError, "overwrite"):
            Project.initialize(root, "Existing", "Adopt engineering discipline")
        project = Project.initialize(root, "Existing", "Adopt engineering discipline", adopt=True)
        self.assertEqual((root / "README.md").read_text(), "Existing application architecture and usage")
        self.assertIn("README.md", project.read()[0]["adoption_preserved"])
        self.assertTrue(project.audit()["ok"])

    def test_dependencies_and_completion_evidence(self):
        first = self.task("First")
        dependent = self.task("Second", depends=[first])
        with self.assertRaisesRegex(UadosError, "Dependency"):
            self.project.claim_task(self.session, dependent)
        self.project.claim_task(self.session, first)
        with self.assertRaisesRegex(UadosError, "Completion requires"):
            self.project.complete_task(self.session, first)
        self.write("code.py", "print('works')\n")
        evidence = self.write("evidence/check.txt", "Verified intended output: works")
        self.project.record_task(self.session, first, "Implemented and checked the output", [evidence])
        self.project.complete_task(self.session, first)
        self.project.claim_task(self.session, dependent)
        self.assertTrue(self.project.audit()["ok"])

    def test_independent_plan_and_result_workflow(self):
        self.write("code.py", "# initial\n")
        task = self.task(risk="major")
        with self.assertRaisesRegex(UadosError, "plan approval"):
            self.project.claim_task(self.session, task)
        evidence = self.write("evidence/design.md", "Considered split writes; tested atomic ledger recovery")
        with self.assertRaisesRegex(UadosError, "different agent"):
            self.project.review_task(self.session, task, "plan", "approve", "Attempted to break the design", [evidence])
        reviewer = self.start("Agent-Reviewer")
        self.project.review_task(reviewer, task, "plan", "approve", "Challenged transactions and path escape; bounded residual risks", [evidence])
        self.refresh(self.session)
        self.project.claim_task(self.session, task)
        self.write("code.py", "print('implemented')\n")
        checks = self.write("evidence/tests.txt", "Regression and recovery checks passed")
        self.project.record_task(self.session, task, "Implemented reviewed design and ran meaningful checks", [checks])
        with self.assertRaisesRegex(UadosError, "result approval"):
            self.project.complete_task(self.session, task)
        self.refresh(reviewer)
        self.project.review_task(reviewer, task, "result", "approve", "Independently exercised intended behavior and failure handling", [evidence])
        self.refresh(self.session)
        self.project.complete_task(self.session, task)
        self.assertEqual(self.project.read()[0]["tasks"][task]["status"], "done")
        self.assertEqual(self.project.read()[0]["phase"], "maintenance")
        self.project.add_task(self.session, "Next milestone", "Plan new accepted work", scopes=["future.py"])
        self.assertEqual(self.project.read()[0]["phase"], "planning")

    def test_overlapping_scopes_prevent_conflicting_task_leases(self):
        first = self.project.add_task(self.session, "Parent", "Change module", scopes=["src"])["task"]
        second = self.project.add_task(self.session, "Child", "Change submodule", scopes=["src/module.py"])["task"]
        self.project.claim_task(self.session, first)
        with self.assertRaisesRegex(UadosError, "Scope overlaps"):
            self.project.claim_task(self.session, second)
        disjoint = self.project.add_task(self.session, "Docs", "Write documentation", scopes=["guides"])["task"]
        self.project.claim_task(self.session, disjoint)

    def test_handover_restores_failures_decisions_and_next_actions(self):
        task = self.task()
        self.project.claim_task(self.session, task)
        self.project.block_task(self.session, task, "First approach failed: fixture lacked the required schema")
        self.project.add_note(self.session, "Failed design", "Split-file commits cannot preserve atomic state", "failure")
        evidence = self.write("evidence/adr.md", "Transactional prototype validated atomic updates")
        self.project.add_decision(self.session, "Use a ledger", "Memory must survive interruption", ["Loose Markdown", "SQLite transaction"], "SQLite", "Atomic state and history with stdlib portability", [evidence], "Trusted local storage only; revisit distributed collaboration")
        self.project.close_session(self.session, "Built core and found fixture defect", ["Repair fixture then resume task"], ["Missing schema"], ["Split-file transaction rejected"])
        replacement = self.project.start_session("Agent-B")
        report = replacement["report"]
        self.assertEqual(report["objective"], "Preserve work across agent changes")
        self.assertTrue(report["failed_approaches"])
        self.assertEqual(report["decisions"][0]["reason"], "Atomic state and history with stdlib portability")
        self.assertEqual(report["latest_handover"]["next"], ["Repair fixture then resume task"])
        self.assertIn("Missing schema", report["latest_handover"]["blockers"])

    def test_projection_failure_is_repairable_without_repeating_action(self):
        with patch("uados.project.write_projections", side_effect=OSError("simulated interrupted write")):
            with self.assertRaisesRegex(UadosError, "committed"):
                self.project.add_note(self.session, "Durable", "Committed before projection failure")
        self.assertFalse(self.project.audit()["ok"])
        self.assertTrue(self.project.audit(repair=True)["ok"])
        state, events, _ = self.project.read()
        self.assertEqual(len(state["notes"]), 1)
        self.assertEqual(events[-1]["kind"], "note.add")

    def test_export_and_git_rebuild_preserve_history(self):
        self.project.add_note(self.session, "Portable", "A future agent can reconstruct this knowledge")
        exported = Path(self.temporary.name) / "handover-copy"
        self.project.export(exported)
        clone = Project(exported)
        self.assertTrue(clone.audit()["ok"])
        (exported / ".uados/ledger.sqlite3").unlink()
        Project.rebuild_ledger(exported)
        restored = Project(exported)
        self.assertTrue(restored.audit()["ok"])
        self.assertEqual(restored.read()[0]["notes"][0]["body"], "A future agent can reconstruct this knowledge")
        with self.assertRaisesRegex(UadosError, "never overwrites"):
            Project.rebuild_ledger(exported)

    def test_experiment_provenance_and_scientific_interpretation(self):
        self.write("experiment.py", "import json\nprint(json.dumps({'mean': 2.0, 'seed': 7}))\n")
        config = self.write("config.json", '{"seed":7}')
        data = self.write("data.csv", "value\n1\n2\n3\n")
        experiment = add_experiment(self.project, self.session, "Deterministic mean", "Mean is 2 for fixture; no population claim", [sys.executable, "experiment.py"], config, [data], 7, ["experiment.py"])["experiment"]
        result = run_experiment(self.project, self.session, experiment, 10)
        self.assertEqual(result["status"], "succeeded")
        self.assertIn('"mean": 2.0', (self.root / result["stdout"]).read_text())
        self.refresh(self.session)
        analysis = self.write("analysis.md", "Mean=2 for three fixture values; not a population estimate")
        conclude_experiment(self.project, self.session, experiment, "Fixture hypothesis supported; uncertainty not estimated", [analysis])
        run = self.project.read()[0]["experiments"][experiment]["runs"][0]
        self.assertEqual(run["returncode"], 0)
        self.assertTrue(run["provenance"]["code_files"])
        self.assertEqual(run["provenance"]["seed"], 7)
        self.assertIn("packages", run["provenance"])
        self.assertTrue(self.project.audit()["ok"])

    def test_cli_json_and_exit_codes(self):
        environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
        status = subprocess.run([sys.executable, "-m", "uados", "--project", str(self.root), "status"], capture_output=True, text=True, env=environment)
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertEqual(json.loads(status.stdout)["name"], "Test project")
        bad = subprocess.run([sys.executable, "-m", "uados", "--project", str(self.root), "task", "claim", "UNKNOWN", "--session", self.session], capture_output=True, text=True, env=environment)
        self.assertEqual(bad.returncode, 2)
        self.assertIn("Unknown task", json.loads(bad.stderr)["error"])


if __name__ == "__main__":
    unittest.main()
