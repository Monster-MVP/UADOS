"""Disposable independently authored mechanical probes; labels are fixtures, not real reviewers."""
import json
import sys
import tempfile
from pathlib import Path

repository = Path(sys.argv[1])
sys.path.insert(0, str(repository / "src"))
from uados.project import Project
from uados.storage import UadosError
from uados import orchestration as orch
from uados import governance as gov


class Fixture:
    def __init__(self, scope="code.py"):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "project"
        self.p = Project.initialize(self.root, "Independent probe", "Verify workflow gates")
        for name in ("plan.txt", "cr.txt", "review.txt", "validation.txt", "code.py"):
            (self.root / name).write_text("Fixture evidence for " + name + "\n", encoding="utf-8")
        self.sessions = {}
        for name in ("Author", "Reviewer1", "Reviewer2", "Reviewer3"):
            r = self.p.start_session(name)
            self.p.acknowledge(r["session"], r["report_hash"])
            self.sessions[name] = r["session"]
            self.call(name, orch.register_agent, ["architecture", "software", "security", "testing"])
        self.task = self.call("Author", self.p.add_task, "Improve runtime", "Acceptance: accountable reviewed result", "major", [scope])["task"]
        self.call("Author", gov.plan_task, self.task, "Implement bounded code change", "Run useful probes", ["plan.txt"])
        self.call("Author", gov.propose_change, self.task, "Missing behavior", "Existing working ledger", ["Do nothing", "Add bounded behavior"], "Add behavior", "Public gates", "Local trust", "Run regression probes", ["cr.txt"])
        self.role_plan = self.roles("Reviewer2")

    def call(self, name, function, *args):
        s = self.sessions[name]
        r = self.p.refresh_session(s)
        assert r["report"]["title"] == "PROJECT UNDERSTANDING REPORT"
        self.p.acknowledge(s, r["report_hash"])
        if getattr(function, "__self__", None) is self.p:
            return function(s, *args)
        return function(self.p, s, *args)

    def roles(self, security):
        plan = self.call("Author", orch.create_roles, self.task)["role_plan"]["id"]
        for role, name in (("implementation", "Author"), ("architecture", "Reviewer1"), ("security", security), ("testing", "Reviewer1")):
            self.call("Author", orch.assign_role, plan, role, name)
        return plan

    def rounds(self, plan=None, stage="plan", veto=None):
        debate = self.call("Author", orch.open_debate, self.task, plan or self.role_plan, stage)["debate"]
        people = sorted(orch.participants(self.p.read()[0], self.p.read()[0]["debates"][debate]))
        analyses = {}
        for name in people:
            analyses[name] = self.call(name, orch.submit_analysis, debate, "Selected additive design", ["Trusted local fixture"], ["Fixtures do not establish real reviewer independence"], ["Keep old behavior"], ["review.txt"])["analysis"]
        self.call("Author", orch.advance_debate, debate)
        for index, name in enumerate(people):
            target = analyses[people[(index + 1) % len(people)]]
            self.call(name, orch.submit_challenge, debate, target, "Stale approval might pass", "Identity is declared", "Preserve old gates", "External authentication absent", ["review.txt"])
        self.call("Author", orch.advance_debate, debate)
        chosen = analyses["Author"]
        for name in people:
            self.call(name, orch.vote, debate, chosen, "request_changes" if name == veto else "approve", "Probe records reason explicitly", ["review.txt"])
        return debate, chosen

    def consensus(self, plan=None, stage="plan"):
        debate, chosen = self.rounds(plan, stage)
        return self.call("Author", orch.finalize, debate, chosen, "All challenges addressed within fixture scope", ["No real model dispatch in probe"])

    def close(self):
        self.tmp.cleanup()


def expect_rejection(function):
    try:
        function()
    except UadosError as error:
        return {"passed": True, "observed_error": str(error)}
    return {"passed": False, "finding": "Operation unexpectedly succeeded"}


def revoked_capability_before_open():
    f = Fixture()
    try:
        f.call("Reviewer1", orch.register_agent, ["security"])
        return expect_rejection(lambda: f.call("Author", orch.open_debate, f.task, f.role_plan, "plan"))
    finally:
        f.close()


def dissent_replacement():
    f = Fixture()
    try:
        debate, chosen = f.rounds(veto="Reviewer2")
        blocked = expect_rejection(lambda: f.call("Author", orch.finalize, debate, chosen, "Ignore veto", ["Risk"]))
        new = f.roles("Reviewer3")
        replacement = expect_rejection(lambda: f.call("Author", orch.open_debate, f.task, new, "plan"))
        return {"passed": blocked["passed"] and replacement["passed"], "veto_blocks_consensus": blocked, "replacing_dissenter_without_replan": replacement}
    finally:
        f.close()


def change_evidence_before_result():
    f = Fixture()
    try:
        f.consensus()
        f.call("Author", f.p.claim_task, f.task)
        (f.root / "code.py").write_text("VALUE = 2\n", encoding="utf-8")
        f.call("Author", f.p.record_task, f.task, "Executed accepted plan", ["validation.txt"])
        (f.root / "cr.txt").write_text("Replaced reviewed change evidence\n", encoding="utf-8")
        return expect_rejection(lambda: f.call("Author", orch.open_debate, f.task, f.role_plan, "result"))
    finally:
        f.close()


def root_scope_self_reference():
    f = Fixture(".")
    try:
        f.consensus()
        f.call("Author", f.p.claim_task, f.task)
        (f.root / "code.py").write_text("VALUE = 2\n", encoding="utf-8")
        f.call("Author", f.p.record_task, f.task, "Validated fixture mutation", ["validation.txt"])
        f.consensus(stage="result")
        f.call("Author", f.p.complete_task, f.task)
        audit = f.p.audit()
        return {"passed": audit["ok"], "completed_status": f.p.read()[0]["tasks"][f.task]["status"], "audit": audit}
    finally:
        f.close()


results = {}
for name, function in (("revoked_capability_before_open", revoked_capability_before_open), ("dissent_replacement", dissent_replacement), ("change_evidence_before_result", change_evidence_before_result), ("root_scope_self_reference", root_scope_self_reference)):
    try:
        results[name] = function()
    except Exception as error:
        results[name] = {"passed": False, "exception": type(error).__name__, "message": str(error)}
print(json.dumps({"kind": "Independent disposable mechanical probes", "not_real_debate": True, "results": results}, indent=2, sort_keys=True))
sys.exit(0 if all(result["passed"] for result in results.values()) else 1)
