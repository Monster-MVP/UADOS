"""Protocol2 acceptance: genuine state transitions, evidence drift and recovery."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from uados.project import Project
from uados.context import context_bundle
from uados import governance as gov, orchestration as orch
from uados.research import add_experiment, run_experiment
from uados.storage import UadosError


class Phase2(unittest.TestCase):
    a: str
    b: str
    c: str

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "project"
        self.p = Project.initialize(self.root, "Phase2", "Accountable software and scientific work")
        self.write("plan.txt", "Design, alternatives, controls, rejection criteria and coverage limitations")
        self.write("checks.txt", "Executed acceptance checks; limitations stated")
        self.write("src/app.py", "VALUE = 1\n")
        self.a = self.session("Builder", "Codex")
        self.b = self.session("Reviewer-A", "Claude Code")
        self.c = self.session("Reviewer-B", "Qoder")

    def write(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return path

    def session(self, name, runtime="other"):
        report = self.p.start_session(name, runtime)
        self.p.acknowledge(report["session"], report["report_hash"])
        return str(report["session"])

    def current(self, session):
        state, events, _ = self.p.read()
        if state["sessions"][session]["context_fingerprint"] != context_bundle(self.root, state, events)["fingerprint"] or not state["sessions"][session]["acknowledged"]:
            report = self.p.refresh_session(session)
            self.p.acknowledge(session, report["report_hash"])

    def act(self, session, function, *args, **kwargs):
        self.current(session)
        return function(self.p, session, *args, **kwargs)

    def task(self, risk="major", scope="src"):
        self.current(self.a)
        task = self.p.add_task(self.a, "Optimize database performance", "Preserve results; measure correct output and resource cost", risk, [scope])["task"]
        self.act(self.a, gov.plan_task, task, "Use the transactional extension", "Exercise failure, independent review and restoration", ["plan.txt"])
        return task

    def roles(self, task, change=True):
        if change:
            self.act(self.a, gov.propose_change, task, "Workflow lacks controls", "Existing system works", ["Keep static gates", "Add executable governance"], "Add governance", "Changes task lifecycle", "Stale evidence", "Exercise all gates", ["plan.txt"])
        for session, caps in ((self.a, ["software"]), (self.b, ["architecture", "security"]), (self.c, ["testing", "performance"])):
            self.act(session, orch.register_agent, caps)
        plan = self.act(self.a, orch.create_roles, task, "software")["role_plan"]
        for role in plan["roles"]:
            name = "Builder" if not role["reviewer"] else "Reviewer-B" if role["id"] in {"testing", "performance"} else "Reviewer-A"
            self.act(self.a, orch.assign_role, plan["id"], role["id"], name)
        return plan["id"]

    def debate(self, task, plan, stage="plan", finish=True):
        debate = self.act(self.a, orch.open_debate, task, plan, stage)["debate"]
        analyses = []
        for session in (self.a, self.b, self.c):
            analyses.append(self.act(session, orch.submit_analysis, debate, "Selected extension " + session, ["Trusted local writers"], ["External identity remains unverified"], ["Documentation only"], ["checks.txt"])["analysis"])
        self.act(self.a, orch.advance_debate, debate)
        for index, session in enumerate((self.a, self.b, self.c)):
            self.act(session, orch.submit_challenge, debate, analyses[(index + 1) % 3], "Could lose evidence", "Identity is a declaration", "Keep old storage", "Hosted platforms unexecuted", ["checks.txt"])
        self.act(self.a, orch.advance_debate, debate)
        if finish:
            for session in (self.a, self.b, self.c):
                self.act(session, orch.vote, debate, analyses[0], "approve", "Challenges addressed within explicit local limits", ["checks.txt"])
            self.act(self.a, orch.finalize, debate, analyses[0], "Preserve tested storage and require evidence-bound new controls", ["Labels are not authentication"])
        return debate, analyses

    def source(self, identifier="paper-1", access="full_text", corpus="Corpus A"):
        return self.act(self.a, gov.add_source, "Primary source", identifier, "https://example.org/" + identifier, "Reported method", "Coverage limited to this source", access, ["plan.txt"], corpus)["source"]

    def idea(self, sources):
        fields = {name: "Explicit, bounded analysis for " + name for name in gov.IDEA_FIELDS}
        return self.act(self.a, gov.add_idea, "Candidate idea", fields, sources, ["plan.txt"])["idea"]

    def test_fresh_protocol2_and_execution_plan(self):
        state, _, _ = self.p.read()
        self.assertEqual(state["protocol_version"], 2)
        report = self.p.start_session("New agent", "ZCode")["report"]
        self.assertTrue(report["execution_plan"])
        self.assertEqual(report["agent_runtime_protocol"], ".agent/startup_protocol.md")
        self.assertTrue((self.root / ".cursor/rules/uados.mdc").is_file())

    def test_routine_requires_plan_and_explained_evidence(self):
        self.current(self.a)
        task = self.p.add_task(self.a, "Small task", "Acceptance criteria", scopes=["src"])["task"]
        with self.assertRaisesRegex(UadosError, "plan before claim"):
            self.p.claim_task(self.a, task)
        self.act(self.a, gov.plan_task, task, "Change fixture", "Check VALUE", ["plan.txt"])
        self.current(self.a)
        self.p.claim_task(self.a, task)
        self.p.record_task(self.a, task, "Verified defined result", ["checks.txt"])
        self.p.complete_task(self.a, task)
        self.assertTrue(self.p.audit()["ok"])

    def test_dynamic_requested_software_and_materials_roles(self):
        software = orch.generate_roles("Optimize database performance", "software")
        self.assertEqual({r["name"] for r in software["roles"]}, {"Architecture Agent", "Backend Engineer Agent", "Performance Agent", "Security Agent", "Testing Agent"})
        research = orch.generate_roles("Develop bacterial cellulose biosensor", "research")
        self.assertEqual(len(research["roles"]), 6)
        self.assertIn("Materials Science Agent", {r["name"] for r in research["roles"]})

    def test_major_requires_current_change_and_real_debate_rounds(self):
        task = self.task()
        plan = self.roles(task, change=False)
        with self.assertRaisesRegex(UadosError, "change request"):
            self.act(self.a, orch.open_debate, task, plan, "plan")
        self.current(self.a)
        with self.assertRaisesRegex(UadosError, "three-round"):
            self.p.claim_task(self.a, task)

    def test_full_major_lifecycle_with_changed_code_and_implemented_change(self):
        task = self.task()
        plan = self.roles(task)
        self.debate(task, plan)
        self.current(self.a)
        self.p.claim_task(self.a, task)
        self.write("src/app.py", "VALUE = 2\n")
        self.p.record_task(self.a, task, "Implemented reviewed change; validated outputs", ["checks.txt"])
        with self.assertRaisesRegex(UadosError, "result consensus"):
            self.p.complete_task(self.a, task)
        self.debate(task, plan, "result")
        self.current(self.a)
        self.p.complete_task(self.a, task)
        state, _, _ = self.p.read()
        self.assertEqual(state["changes"][state["tasks"][task]["change"]]["status"], "implemented")
        self.assertIn("selected_approach", (self.root / "CONSENSUS_DECISION.md").read_text())
        self.assertTrue(self.p.audit()["ok"])

    def test_one_review_label_cannot_satisfy_role_quorum(self):
        task = self.task()
        self.act(self.a, gov.propose_change, task, "P", "B", ["A", "B"], "D", "I", "R", "V", ["plan.txt"])
        self.act(self.a, orch.register_agent, ["software"])
        self.act(self.b, orch.register_agent, ["architecture", "security", "testing", "performance"])
        plan = self.act(self.a, orch.create_roles, task, "software")["role_plan"]
        for role in plan["roles"]:
            self.act(self.a, orch.assign_role, plan["id"], role["id"], "Reviewer-A" if role["reviewer"] else "Builder")
        with self.assertRaisesRegex(UadosError, "two independent"):
            self.act(self.a, orch.open_debate, task, plan["id"], "plan")

    def test_vote_before_rounds_and_self_challenge_rejected(self):
        task = self.task()
        plan = self.roles(task)
        debate = self.act(self.a, orch.open_debate, task, plan, "plan")["debate"]
        with self.assertRaisesRegex(UadosError, "Voting"):
            self.act(self.b, orch.vote, debate, "invented", "approve", "No analysis yet", ["checks.txt"])
        analysis = self.act(self.a, orch.submit_analysis, debate, "A", ["A"], ["R"], ["B"], ["checks.txt"])["analysis"]
        with self.assertRaisesRegex(UadosError, "Every assigned"):
            self.act(self.a, orch.advance_debate, debate)
        for session in (self.b, self.c):
            self.act(session, orch.submit_analysis, debate, "B", ["A"], ["R"], ["C"], ["checks.txt"])
        self.act(self.a, orch.advance_debate, debate)
        with self.assertRaisesRegex(UadosError, "another participant"):
            self.act(self.a, orch.submit_challenge, debate, analysis, "F", "U", "A", "M", ["checks.txt"])

    def test_assignment_freeze_and_capability_staleness(self):
        task = self.task()
        plan = self.roles(task)
        self.act(self.b, orch.register_agent, ["architecture"])
        with self.assertRaisesRegex(UadosError, "required capability"):
            self.act(self.a, orch.open_debate, task, plan, "plan")
        self.act(self.b, orch.register_agent, ["architecture", "security"])
        debate = self.act(self.a, orch.open_debate, task, plan, "plan")["debate"]
        with self.assertRaisesRegex(UadosError, "frozen"):
            self.act(self.a, orch.assign_role, plan, "security", "Reviewer-A")
        self.act(self.b, orch.register_agent, ["architecture", "security", "new-capability"])
        with self.assertRaisesRegex(UadosError, "stale"):
            self.act(self.a, orch.submit_analysis, debate, "A", ["A"], ["R"], ["B"], ["checks.txt"])

    def test_dissent_cannot_be_hidden_by_another_debate_or_plan(self):
        task = self.task()
        plan = self.roles(task)
        debate, analyses = self.debate(task, plan, finish=False)
        self.act(self.b, orch.vote, debate, analyses[0], "request_changes", "Evidence misses a failure path", ["checks.txt"])
        with self.assertRaisesRegex(UadosError, "previous dissent"):
            self.act(self.a, orch.open_debate, task, plan, "plan")
        with self.assertRaisesRegex(UadosError, "explicit task replan"):
            self.act(self.a, gov.plan_task, task, "Same plan relabeled", "Same checks", ["plan.txt"])
        self.act(self.a, gov.replan_task, task, "Address missing failure path; preserve previous objection")
        self.assertTrue(self.p.read()[0]["debates"][debate]["votes"])

    def test_cr_and_debate_evidence_drift_invalidates_approval(self):
        task = self.task()
        plan = self.roles(task)
        self.debate(task, plan)
        self.write("plan.txt", "Different decision evidence")
        self.current(self.a)
        with self.assertRaisesRegex(UadosError, "Evidence changed"):
            self.p.claim_task(self.a, task)

    def test_generated_root_scope_does_not_self_invalidate(self):
        task = self.task(scope=".")
        plan = self.roles(task)
        self.debate(task, plan)
        self.current(self.a)
        self.p.claim_task(self.a, task)
        self.assertEqual(self.p.read()[0]["tasks"][task]["status"], "in_progress")

    def test_hidden_adapter_policy_change_invalidates_context(self):
        self.write(".cursor/rules/uados.mdc", "---\nalwaysApply: true\n---\nRead an amended master workflow\n")
        with self.assertRaisesRegex(UadosError, "context changed"):
            self.p.add_note(self.a, "Stale", "Must refresh adapter context")

    def test_novelty_rejects_inaccessible_abstract_and_correlated_sources(self):
        for access in ("unavailable", "abstract"):
            source = self.source("source-" + access, access)
            idea = self.idea([source])
            with self.assertRaisesRegex(UadosError, "two distinct"):
                self.act(self.b, gov.review_idea, idea, "candidate", "Unsupported positive claim", ["checks.txt"])
            self.act(self.b, gov.review_idea, idea, "inconclusive", "Source access insufficient", ["checks.txt"])
        first = self.source("chapter-a", corpus="Same handbook")
        second = self.source("chapter-b", corpus="Same handbook")
        idea = self.idea([first, second])
        with self.assertRaisesRegex(UadosError, "distinct accessed full-text corpora"):
            self.act(self.b, gov.review_idea, idea, "candidate", "Related chapters do not prove coverage", ["checks.txt"])

    def test_distinct_fulltexts_allow_only_provisional_independent_candidate(self):
        idea = self.idea([self.source("one", corpus="Paper A"), self.source("two", corpus="Paper B")])
        with self.assertRaisesRegex(UadosError, "author"):
            self.act(self.a, gov.review_idea, idea, "candidate", "Self-review", ["checks.txt"])
        result = self.act(self.b, gov.review_idea, idea, "candidate", "Candidate scoped to declared corpus; wider novelty remains uncertain", ["checks.txt"])
        self.assertIn("provisional", result["review"]["meaning"])
        with self.assertRaisesRegex(UadosError, "Duplicate"):
            self.source("ONE")

    def test_research_export_retains_evidence_and_changed_bytes_fail_audit(self):
        idea = self.idea([self.source()])
        self.act(self.b, gov.review_idea, idea, "overlap", "Known method; no novelty established", ["checks.txt"])
        destination = Path(self.temporary.name) / "portable"
        self.p.export(destination)
        self.assertTrue((destination / "plan.txt").is_file())
        self.assertTrue(Project(destination).audit()["ok"])
        self.write("plan.txt", "Changed accessed-source evidence")
        self.assertFalse(self.p.audit()["ok"])

    def test_exact_hypothesis_run_and_operational_failure_distinguished(self):
        idea = self.idea([self.source()])
        hypothesis = self.act(self.a, gov.add_hypothesis, idea, "Metric equals 2", "Reference fixture", "Measured value", "Value differs", "No population inference", ["plan.txt"])["hypothesis"]
        self.write("config.json", '{"seed":7}')
        experiment = self.act(self.a, add_experiment, "Failure fixture", "Metric equals 2", [sys.executable, "-c", "raise SystemExit(1)"], "config.json", [], 7, ["src"], hypothesis_id=hypothesis)["experiment"]
        run = self.act(self.a, run_experiment, experiment, 10)
        with self.assertRaisesRegex(UadosError, "cannot be a scientific"):
            self.act(self.a, gov.conclude_hypothesis, hypothesis, experiment, run["run"], "refuted", "Process failed, not the hypothesis", ["checks.txt"])
        self.act(self.a, gov.conclude_hypothesis, hypothesis, experiment, run["run"], "inconclusive", "Operational failure; no scientific test completed", ["checks.txt"])

    def test_explicit_upgrade_preserves_event_prefix_and_legacy_task(self):
        root = Path(self.temporary.name) / "legacy"
        p = Project.initialize(root, "Legacy", "Preserve history", protocol_version=1)
        (root / "evidence.txt").write_text("Upgrade plan challenged and verified")
        report = p.start_session("Old builder")
        owner = report["session"]
        p.acknowledge(owner, report["report_hash"])
        task = p.add_task(owner, "Upgrade", "Add v2 without rewriting v1", "major", ["source.py"])["task"]
        review = p.start_session("Old reviewer")
        p.acknowledge(review["session"], review["report_hash"])
        p.review_task(review["session"], task, "plan", "approve", "Preserve old event prefix and interpretation", ["evidence.txt"])
        report = p.refresh_session(owner)
        p.acknowledge(owner, report["report_hash"])
        p.claim_task(owner, task)
        prefix = [e["hash"] for e in p.read()[1]]
        p.upgrade(owner, task)
        state, events, _ = p.read()
        self.assertEqual(prefix, [e["hash"] for e in events[:len(prefix)]])
        self.assertEqual(state["tasks"][task]["protocol_version"], 1)
        self.assertEqual(state["protocol_version"], 2)
        self.assertTrue(p.audit()["ok"])

    def test_audit_improvement_record_is_proposed_and_deduplicated(self):
        self.write("ENGINEERING_RULES/security.md", "Rules changed while session was active")
        audit = dict(self.p.audit(), errors=["Missing workflow control: reproduction instructions"], ok=False)
        result = gov.record_audit(self.p, self.a, audit)
        self.assertEqual(len(result["recorded"]), 1)
        count = len(self.p.read()[1])
        again = gov.record_audit(self.p, self.a, audit)
        self.assertEqual(again["recorded"], [])
        self.assertEqual(count, len(self.p.read()[1]))
        item = next(iter(self.p.read()[0]["improvements"].values()))
        self.assertEqual(item["status"], "proposed")
        self.assertIn("Undetermined", item["root_cause"])

    def test_handover_structured_snapshot_survives_rebuild_and_fresh_process(self):
        task = self.task(risk="routine")
        self.current(self.a)
        self.p.claim_task(self.a, task)
        self.p.block_task(self.a, task, "Required dataset unavailable; no measurements")
        self.p.close_session(self.a, "Logical Day1: half completed", ["Resume remaining task after obtaining data"], ["Dataset unavailable"], ["Initial input format rejected"])
        destination = Path(self.temporary.name) / "day30"
        self.p.export(destination)
        (destination / ".uados/ledger.sqlite3").unlink()
        Project.rebuild_ledger(destination)
        environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
        r = subprocess.run([sys.executable, "-m", "uados", "--project", str(destination), "session", "start", "--agent", "Day30-Codex", "--runtime", "Codex"], env=environment, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        report = json.loads(r.stdout)["report"]
        self.assertIn(task, " ".join(report["latest_handover"]["project_snapshot"]["remaining_tasks"]))
        self.assertIn("Dataset unavailable", report["latest_handover"]["blockers"])

    def test_role_generation_cannot_replace_another_authors_plan(self):
        task = self.task()
        with self.assertRaisesRegex(UadosError, "author or owner"):
            self.act(self.b, orch.create_roles, task, "software")

    def test_claim_requires_selected_implementer_and_current_role_consensus(self):
        task = self.task()
        plan = self.roles(task)
        self.debate(task, plan)
        third = self.session("Third implementer")
        self.current(third)
        with self.assertRaisesRegex(UadosError, "selected nonreview"):
            self.p.claim_task(third, task)
        self.act(third, orch.register_agent, ["software"])
        replacement = self.act(self.a, orch.create_roles, task, "software")["role_plan"]["id"]
        self.act(self.a, orch.assign_role, replacement, "implementation", "Third implementer")
        self.current(third)
        with self.assertRaisesRegex(UadosError, "consensus"):
            self.p.claim_task(third, task)

    def test_author_cannot_revoke_another_active_lease_by_replanning(self):
        task = self.task(risk="routine")
        self.current(self.b)
        self.p.claim_task(self.b, task)
        with self.assertRaisesRegex(UadosError, "active lease"):
            self.act(self.a, gov.replan_task, task, "Switch contributor")
        self.assertEqual(self.p.read()[0]["tasks"][task]["owner"], self.b)

    def test_arbitrary_cr_prefixed_files_are_maintained_scope(self):
        from uados.storage import scope_snapshot
        self.write("CHANGE_REQUESTS/CRITICAL_SECURITY.md", "Maintained policy")
        self.write("CHANGE_REQUESTS/CR_parser.py", "VALUE = 1")
        self.write("CHANGE_REQUESTS/CR000001.md", "Generated projection")
        snapshot = scope_snapshot(self.root, ["CHANGE_REQUESTS"])
        self.assertIn("CHANGE_REQUESTS/CRITICAL_SECURITY.md", snapshot)
        self.assertIn("CHANGE_REQUESTS/CR_parser.py", snapshot)
        self.assertNotIn("CHANGE_REQUESTS/CR000001.md", snapshot)
        self.assertIn("CHANGE_REQUESTS/CR_TEMPLATE.md", snapshot)

    def test_research_policy_change_stales_task_consensus_and_novelty(self):
        task = self.task()
        plan = self.roles(task)
        self.debate(task, plan)
        idea = self.idea([self.source()])
        self.act(self.b, gov.review_idea, idea, "overlap", "Known method", ["checks.txt"])
        self.write("RESEARCH_MANAGEMENT/innovation_policy.md", "Revised assessment controls")
        self.current(self.a)
        with self.assertRaisesRegex(UadosError, "consensus"):
            self.p.claim_task(self.a, task)
        self.assertTrue(any("Stale novelty assessment" in value for value in self.p.audit()["warnings"]))

    def test_linked_source_change_before_execution_is_rejected(self):
        idea = self.idea([self.source()])
        hypothesis = self.act(self.a, gov.add_hypothesis, idea, "Metric equals 2", "Fixture", "Value", "Not 2", "Limited", ["checks.txt"])["hypothesis"]
        self.write("config.json", "{}")
        experiment = self.act(self.a, add_experiment, "Probe", "Metric equals 2", [sys.executable, "-c", "print(2)"], "config.json", [], 7, ["src"], hypothesis_id=hypothesis)["experiment"]
        self.write("plan.txt", "Literature evidence replaced after registration")
        with self.assertRaisesRegex(UadosError, "Evidence changed"):
            self.act(self.a, run_experiment, experiment, 10)
        self.assertEqual(self.p.read()[0]["experiments"][experiment]["runs"], [])

    def test_malformed_record_arrays_return_json_error_without_event(self):
        self.write("bad.json", json.dumps({"title": "x", "identifier": "x", "url": "https://example.org/x", "claim": "x", "limitation": "x", "access": "unavailable", "evidence": [7], "corpus": "x"}))
        count = len(self.p.read()[1])
        environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
        result = subprocess.run([sys.executable, "-m", "uados", "--project", str(self.root), "research", "source", "--record", "bad.json", "--session", self.a], env=environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("nonempty string", json.loads(result.stderr)["error"])
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(len(self.p.read()[1]), count)

    def test_result_debate_rejects_files_changed_after_submission(self):
        task = self.task()
        plan = self.roles(task)
        self.debate(task, plan)
        self.current(self.a)
        self.p.claim_task(self.a, task)
        self.p.record_task(self.a, task, "Submitted", ["checks.txt"])
        self.write("src/app.py", "VALUE = 3")
        with self.assertRaisesRegex(UadosError, "changed after submission"):
            self.act(self.a, orch.open_debate, task, plan, "result")

    def test_superseded_change_evidence_remains_history_without_blocking_current_audit(self):
        task = self.task()
        plan = self.roles(task)
        old = self.p.read()[0]["tasks"][task]["change"]
        self.debate(task, plan)
        self.act(self.a, gov.replan_task, task, "Supersede the first change with a current evidence packet")
        self.act(self.a, gov.plan_task, task, "Revised acceptance", "Run a fresh review", ["plan.txt"])
        self.act(self.a, gov.propose_change, task, "Revised", "Prior proposal superseded", ["Old", "New"], "New", "Current", "Declared limits", "Run checks", ["checks.txt"])
        self.assertNotEqual(self.p.read()[0]["tasks"][task]["change"], old)
        self.assertTrue(self.p.audit()["ok"])

    def test_snapshot_retains_two_versions_and_export_rebuild_preserves_history(self):
        from uados.storage import scope_snapshot
        task = self.task()
        plan = self.roles(task)
        first = self.p.read()[0]["changes"][self.p.read()[0]["tasks"][task]["change"]]["evidence"][0]
        self.act(self.a, gov.replan_task, task, "Use new evidence without erasing prior bytes")
        self.write("plan.txt", "Revised design and evidence bytes")
        self.act(self.a, gov.plan_task, task, "Revised", "Fresh checks", ["plan.txt"])
        self.act(self.a, gov.propose_change, task, "Revised", "Superseded", ["Old", "New"], "New", "Current", "Limits", "Verify", ["plan.txt"])
        second = self.p.read()[0]["changes"][self.p.read()[0]["tasks"][task]["change"]]["evidence"][0]
        self.assertNotEqual(first["snapshot"], second["snapshot"])
        self.assertEqual((self.root / first["snapshot"]).read_text(), "Design, alternatives, controls, rejection criteria and coverage limitations")
        self.assertEqual((self.root / second["snapshot"]).read_text(), "Revised design and evidence bytes")
        self.assertFalse(any(p.startswith(".uados/") for p in scope_snapshot(self.root, ["."])))
        audit = self.p.audit()
        self.assertTrue(audit["ok"])
        self.assertTrue(audit["history_ok"])
        self.assertTrue(audit["archived_originals"])
        destination = Path(self.temporary.name) / "snapshot-export"
        self.p.export(destination)
        (destination / ".uados/ledger.sqlite3").unlink()
        Project.rebuild_ledger(destination)
        self.assertTrue((destination / first["snapshot"]).is_file())
        self.assertTrue(Project(destination).audit()["history_ok"])

    def test_snapshot_does_not_authorize_edited_live_evidence(self):
        task = self.task(risk="routine")
        proof = self.p.read()[0]["tasks"][task]["plan"]["evidence"][0]
        self.write("plan.txt", "Changed live design")
        self.assertTrue((self.root / proof["snapshot"]).is_file())
        self.current(self.a)
        with self.assertRaisesRegex(UadosError, "Evidence changed"):
            self.p.claim_task(self.a, task)

    def test_corrupt_preexisting_snapshot_cannot_be_overwritten(self):
        import hashlib
        from uados.storage import evidence_files
        content = b"New exact evidence\r\n\xff"
        path = self.root / "new-proof.bin"
        path.write_bytes(content)
        archive = self.root / (".uados/evidence/sha256/" + hashlib.sha256(content).hexdigest())
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_bytes(b"Corrupt object")
        count = len(self.p.read()[1])
        with self.assertRaisesRegex(UadosError, "snapshot is corrupt"):
            evidence_files(self.root, ["new-proof.bin"])
        self.assertEqual(archive.read_bytes(), b"Corrupt object")
        self.assertEqual(count, len(self.p.read()[1]))

    def test_missing_or_corrupt_historical_snapshot_is_integrity_error(self):
        task = self.task()
        self.roles(task)
        proof = self.p.read()[0]["tasks"][task]["plan"]["evidence"][0]
        self.act(self.a, gov.replan_task, task, "Superseded but retain proof")
        (self.root / proof["snapshot"]).write_bytes(b"Corrupt preserved original")
        audit = self.p.audit()
        self.assertFalse(audit["ok"])
        self.assertTrue(any("snapshot corrupt" in value for value in audit["errors"]))
        (self.root / proof["snapshot"]).unlink()
        self.assertTrue(any("snapshot unavailable" in value for value in self.p.audit()["errors"]))

    def test_legacy_missing_original_is_explicit_historical_warning(self):
        from uados.storage import file_hash
        self.write("legacy-proof.txt", "Old legacy bytes")
        self.current(self.a)
        def legacy_record(state, events, session):
            state["changes"]["CR999999"] = {"id": "CR999999", "task": "not-active", "evidence": [{"path": "legacy-proof.txt", "sha256": file_hash(self.root / "legacy-proof.txt"), "bytes": 16}]}
        self.p.mutate("legacy.fixture", "Legacy evidence record with no promised snapshot", legacy_record, self.a)
        self.write("legacy-proof.txt", "Replacement bytes cannot recreate original")
        audit = self.p.audit()
        self.assertTrue(audit["ok"])
        self.assertFalse(audit["history_ok"])
        self.assertTrue(any("Unrecoverable historical evidence" in value for value in audit["warnings"]))

    def test_snapshot_binding_rejects_alternate_path_and_symlink(self):
        from uados.storage import evidence_files, snapshot_problems
        proof = evidence_files(self.root, ["checks.txt"])[0]
        alternate = dict(proof, snapshot="checks.txt")
        self.assertTrue(snapshot_problems(self.root, alternate))
        archive = self.root / proof["snapshot"]
        archive.unlink()
        archive.symlink_to(self.root / "checks.txt")
        self.assertTrue(snapshot_problems(self.root, proof))

    def test_handover_export_preserves_unavailable_planned_scope(self):
        task = self.task(risk="routine", scope="unavailable/data.csv")
        self.current(self.a)
        self.p.claim_task(self.a, task)
        self.p.block_task(self.a, task, "Required dataset unavailable, not empty")
        destination = Path(self.temporary.name) / "missing-scope-export"
        result = self.p.export(destination)
        self.assertEqual(result["unavailable_scopes"], ["unavailable/data.csv"])
        self.assertFalse((destination / "unavailable/data.csv").exists())
        self.assertEqual(Project(destination).read()[0]["tasks"][task]["status"], "blocked")
        self.assertTrue(Project(destination).audit()["ok"])


if __name__ == "__main__":
    unittest.main()
