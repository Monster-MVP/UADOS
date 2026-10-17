"""JSON CLI: deterministic interfaces for humans and different agent runtimes."""

import argparse
import json
import sqlite3
import sys

from . import __version__
from .context import context_bundle
from .project import Project
from .research import add_experiment, conclude_experiment, resolve_experiment, run_experiment
from .storage import UadosError
from .storage import safe_path
from .protocol import RUNTIMES
from . import governance as gov
from . import orchestration as orch


def parser():
    root = argparse.ArgumentParser(description="Universal Agentic Development Operating System")
    root.add_argument("--version", action="version", version=__version__)
    root.add_argument("--project", default=".", help="Project root; place this before the command")
    commands = root.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Initialize a project without overwriting existing files")
    init.add_argument("path")
    init.add_argument("--name", required=True)
    init.add_argument("--objective", required=True)
    init.add_argument("--mode", choices=("auto", "software", "research", "hybrid"), default="auto")
    init.add_argument("--adopt", action="store_true", help="Preserve existing maintained documents; generated-path collisions still fail")
    init.add_argument("--protocol-version", type=int, choices=(1, 2), default=2, help="Fresh projects default to protocol2; 1 supports legacy workflow reproduction")
    commands.add_parser("status", help="Read durable state and report projection drift")
    commands.add_parser("rebuild-ledger", help="Reconstruct a missing local database from validated JSON exports")
    context = commands.add_parser("context", help="Read context manifest or full context documents")
    context.add_argument("--full", action="store_true")
    audit = commands.add_parser("audit", help="Check ledger, memory and referenced evidence")
    audit.add_argument("--repair", action="store_true", help="Rebuild generated views; never repairs corrupt evidence/history")
    audit.add_argument("--record", action="store_true", help="Record proposed improvement findings with an acknowledged session")
    audit.add_argument("--session")
    upgrade = commands.add_parser("upgrade", help="Explicitly enable protocol2, preserving history and legacy tasks")
    upgrade.add_argument("--session", required=True)
    upgrade.add_argument("--task", required=True)
    adapter = commands.add_parser("adapter", help="Generate a central-workflow bootstrap packet for a supported runtime")
    adapter.add_argument("--runtime", choices=RUNTIMES, required=True)
    adapter.add_argument("--agent", default="AGENT_ID")
    export = commands.add_parser("export", help="Create a portable context/evidence project directory")
    export.add_argument("path")
    export.add_argument("--include", action="append", default=[], help="Additional project-relative file/directory")

    trust = commands.add_parser("trust", help="Optional external SSHSIG ledger checkpoints").add_subparsers(dest="action", required=True)
    checkpoint = trust.add_parser("checkpoint", help="Sign a current audit/ledger snapshot into a new external bundle")
    checkpoint.add_argument("--output", required=True)
    checkpoint.add_argument("--principal", required=True)
    checkpoint.add_argument("--key", required=True, help="External operator signing key; never stored in project records")
    verify = trust.add_parser("verify", help="Verify an external pinned checkpoint with authorized OpenSSH signers")
    verify.add_argument("--bundle", required=True)
    verify.add_argument("--principal", required=True)
    verify.add_argument("--expected-sha256", required=True, help="Digest obtained from a trusted external source")
    verify.add_argument("--allowed-signers", required=True, help="External OpenSSH authorization policy")
    verify.add_argument("--revocations", help="External OpenSSH revoked-keys file or KRL")
    verify.add_argument("--require-current", action="store_true", help="Reject a valid checkpoint covering only a historical prefix")

    dispatch_cmd = commands.add_parser("dispatch", help="Provider-neutral local dispatch receipt boundary").add_subparsers(dest="action", required=True)
    dispatch_run = dispatch_cmd.add_parser("run", help="Run the deterministic local fake adapter")
    dispatch_run.add_argument("--request", required=True, help="Project-relative canonical request JSON")
    dispatch_run.add_argument("--output", required=True, help="New external receipt file")
    dispatch_verify = dispatch_cmd.add_parser("verify", help="Verify a local dispatch receipt")
    dispatch_verify.add_argument("--request", required=True)
    dispatch_verify.add_argument("--receipt", required=True)

    coordination = commands.add_parser("coordination", help="Read-only coordination and history boundary")
    coordination_sub = coordination.add_subparsers(dest="action", required=True)
    coordination_sub.add_parser("benchmark", help="Measure local SQLite history without mutation")

    session = commands.add_parser("session").add_subparsers(dest="action", required=True)
    start = session.add_parser("start")
    start.add_argument("--agent", required=True)
    start.add_argument("--runtime", choices=RUNTIMES, default="other")
    refresh = session.add_parser("refresh")
    refresh.add_argument("session_id")
    acknowledge = session.add_parser("acknowledge")
    acknowledge.add_argument("session_id")
    acknowledge.add_argument("--report-hash", required=True)
    close = session.add_parser("close")
    close.add_argument("session_id")
    close.add_argument("--summary", required=True)
    close.add_argument("--next", action="append", required=True)
    close.add_argument("--blocker", action="append", default=[])
    close.add_argument("--failed", action="append", default=[])

    task = commands.add_parser("task").add_subparsers(dest="action", required=True)
    add = task.add_parser("add")
    add.add_argument("--title", required=True)
    add.add_argument("--description", required=True, help="Scope, intent and acceptance criteria")
    add.add_argument("--risk", choices=("routine", "major"), default="routine")
    add.add_argument("--scope", action="append", default=[])
    add.add_argument("--depends", action="append", default=[])
    claim = task.add_parser("claim")
    claim.add_argument("task_id")
    claim.add_argument("--lease-minutes", type=int, default=60)
    claim.add_argument("--takeover-reason")
    record = task.add_parser("record")
    record.add_argument("task_id")
    record.add_argument("--summary", required=True)
    record.add_argument("--evidence", action="append", required=True)
    review = task.add_parser("review")
    review.add_argument("task_id")
    review.add_argument("--stage", choices=("plan", "result"), required=True)
    review.add_argument("--verdict", choices=("approve", "request_changes"), required=True)
    review.add_argument("--challenge", required=True)
    review.add_argument("--evidence", action="append", required=True)
    complete = task.add_parser("complete")
    complete.add_argument("task_id")
    block = task.add_parser("block")
    block.add_argument("task_id")
    block.add_argument("--reason", required=True)
    plan = task.add_parser("plan")
    plan.add_argument("task_id")
    plan.add_argument("--implementation", required=True)
    plan.add_argument("--validation", required=True)
    plan.add_argument("--evidence", action="append", required=True)
    replan = task.add_parser("replan")
    replan.add_argument("task_id")
    replan.add_argument("--reason", required=True)
    replan.add_argument("--description")
    replan.add_argument("--scope", action="append")
    for subparser in (add, claim, record, review, complete, block, plan, replan):
        subparser.add_argument("--session", required=True)

    agent = commands.add_parser("agent").add_subparsers(dest="action", required=True).add_parser("register")
    agent.add_argument("--session", required=True)
    agent.add_argument("--capability", action="append", required=True)
    roles = commands.add_parser("roles").add_subparsers(dest="action", required=True)
    role_gen = roles.add_parser("generate")
    role_gen.add_argument("task_id")
    role_gen.add_argument("--type", choices=("auto", "software", "research", "hybrid"), default="auto")
    role_gen.add_argument("--session", required=True)
    role_select = roles.add_parser("select")
    role_select.add_argument("role_plan_id")
    role_assign = roles.add_parser("assign")
    role_assign.add_argument("role_plan_id")
    role_assign.add_argument("--role", required=True)
    role_assign.add_argument("--agent", required=True)
    role_assign.add_argument("--session", required=True)
    debates = commands.add_parser("debate").add_subparsers(dest="action", required=True)
    debate_open = debates.add_parser("open")
    debate_open.add_argument("task_id")
    debate_open.add_argument("--roles", required=True)
    debate_open.add_argument("--stage", choices=("plan", "result"), required=True)
    analysis = debates.add_parser("analysis")
    analysis.add_argument("--solution", required=True)
    for field in ("assumption", "risk", "alternative", "evidence"):
        analysis.add_argument("--" + field, action="append", required=True)
    challenge = debates.add_parser("challenge")
    for field in ("target", "failure", "unsupported", "alternative", "missing-evidence"):
        challenge.add_argument("--" + field, required=True)
    challenge.add_argument("--evidence", action="append", required=True)
    advance = debates.add_parser("advance")
    vote = debates.add_parser("vote")
    vote.add_argument("--select", required=True)
    vote.add_argument("--verdict", choices=("approve", "request_changes"), required=True)
    vote.add_argument("--reason", required=True)
    vote.add_argument("--evidence", action="append", required=True)
    consensus = debates.add_parser("consensus")
    consensus.add_argument("--select", required=True)
    consensus.add_argument("--reason", required=True)
    consensus.add_argument("--risk", action="append", required=True)
    for subparser in (analysis, challenge, advance, vote, consensus):
        subparser.add_argument("debate_id")
    for subparser in (debate_open, analysis, challenge, advance, vote, consensus):
        subparser.add_argument("--session", required=True)
    packet = debates.add_parser("packet")
    packet.add_argument("debate_id")
    packet.add_argument("--agent", required=True)
    change = commands.add_parser("change").add_subparsers(dest="action", required=True).add_parser("propose")
    change.add_argument("task_id")
    change.add_argument("--record", required=True, help="Project-relative JSON request with all seven fields, alternatives and evidence")
    change.add_argument("--session", required=True)

    note = commands.add_parser("note")
    note.add_argument("--session", required=True)
    note.add_argument("--title", required=True)
    note.add_argument("--body", required=True)
    note.add_argument("--kind", choices=("technical", "lesson", "failure", "research"), default="technical")

    decision = commands.add_parser("decision").add_subparsers(dest="action", required=True).add_parser("add")
    decision.add_argument("--session", required=True)
    for field in ("title", "problem", "decision", "reason", "risk"):
        decision.add_argument("--" + field, required=True)
    decision.add_argument("--alternatives", action="append", required=True)
    decision.add_argument("--evidence", action="append", required=True)
    decision.add_argument("--task", help="Major reviewed task; decision remains proposed until task completion")

    experiment = commands.add_parser("experiment").add_subparsers(dest="action", required=True)
    exp_add = experiment.add_parser("add")
    for field in ("title", "hypothesis", "command-json", "config"):
        exp_add.add_argument("--" + field, required=True)
    exp_add.add_argument("--dataset", action="append", default=[])
    exp_add.add_argument("--seed", type=int, required=True)
    exp_add.add_argument("--scope", action="append", required=True)
    exp_add.add_argument("--cwd", default=".")
    exp_add.add_argument("--hypothesis-id")
    exp_run = experiment.add_parser("run")
    exp_run.add_argument("experiment_id")
    exp_run.add_argument("--timeout", type=float, default=3600)
    resolve = experiment.add_parser("resolve")
    resolve.add_argument("experiment_id")
    resolve.add_argument("--reason", required=True)
    conclude = experiment.add_parser("conclude")
    conclude.add_argument("experiment_id")
    conclude.add_argument("--conclusion", required=True)
    conclude.add_argument("--evidence", action="append", required=True)
    for subparser in (exp_add, exp_run, resolve, conclude):
        subparser.add_argument("--session", required=True)
    research = commands.add_parser("research").add_subparsers(dest="action", required=True)
    for operation in ("source", "idea", "hypothesis"):
        form = research.add_parser(operation)
        form.add_argument("--record", required=True, help="Project-relative structured JSON record")
        form.add_argument("--session", required=True)
    novelty = research.add_parser("novelty")
    novelty.add_argument("idea_id")
    novelty.add_argument("--verdict", choices=("candidate", "overlap", "inconclusive"), required=True)
    novelty.add_argument("--challenge", required=True)
    novelty.add_argument("--evidence", action="append", required=True)
    novelty.add_argument("--session", required=True)
    outcome = research.add_parser("outcome")
    outcome.add_argument("hypothesis_id")
    outcome.add_argument("--experiment", required=True)
    outcome.add_argument("--run", required=True)
    outcome.add_argument("--verdict", choices=("supported", "refuted", "inconclusive"), required=True)
    outcome.add_argument("--reason", required=True)
    outcome.add_argument("--evidence", action="append", required=True)
    outcome.add_argument("--session", required=True)
    improvement = commands.add_parser("improvement")
    improvement.add_argument("--record", required=True)
    improvement.add_argument("--session", required=True)
    return root


def read_record(project, relative, fields):
    try:
        value = json.loads(safe_path(project.root, relative).read_text(encoding="utf-8"))
    except ValueError as exc:
        raise UadosError("Record must be valid JSON: " + relative) from exc
    if not isinstance(value, dict) or any(field not in value for field in fields):
        raise UadosError("Record requires fields: " + ", ".join(fields))
    for field in fields:
        expected = dict if field == "fields" else list if field in {"alternatives", "sources", "evidence"} else str
        if not isinstance(value[field], expected):
            raise UadosError("Invalid record field type: " + field)
        if expected is list and any(not isinstance(item, str) or not item.strip() for item in value[field]):
            raise UadosError("Record field requires nonempty string elements: " + field)
    return [value[field] for field in fields]


def dispatch(args):
    if args.command == "init":
        project = Project.initialize(args.path, args.name, args.objective, args.mode, args.adopt, args.protocol_version)
        state = project.read()[0]
        return {"project": str(project.root), "mode": state["mode"], "protocol_version": state["protocol_version"], "preserved_files": state["adoption_preserved"]}
    if args.command == "rebuild-ledger":
        return Project.rebuild_ledger(args.project)
    project = Project(args.project)
    if args.command == "trust":
        from .trust import create_checkpoint, verify_checkpoint
        if args.action == "checkpoint":
            return create_checkpoint(project, args.output, args.principal, args.key)
        return verify_checkpoint(project, args.bundle, args.principal, args.expected_sha256,
                                 args.allowed_signers, args.revocations, args.require_current)
    if args.command == "dispatch":
        from .dispatch import run_dispatch, verify_receipt
        if args.action == "run":
            return run_dispatch(project, args.request, args.output)
        return verify_receipt(project, args.request, args.receipt)
    if args.command == "coordination":
        from .coordination import benchmark_history
        return benchmark_history(project)
    if args.command == "status":
        state, events, drift = project.read()
        return {"name": state["name"], "objective": state["objective"], "mode": state["mode"], "phase": state["phase"], "event_count": len(events), "tasks": state["tasks"], "experiments": state["experiments"], "active_sessions": [s["id"] for s in state["sessions"].values() if s["status"] == "active"], "projection_drift": drift}
    if args.command == "context":
        state, events, _ = project.read(strict=True)
        bundle = context_bundle(project.root, state, events)
        if not args.full:
            bundle["documents"] = sorted(bundle["documents"])
        return bundle
    if args.command == "audit":
        before = project.audit()
        result = project.audit(True) if args.repair else before
        if args.record:
            if not args.session:
                raise UadosError("audit --record needs an acknowledged --session; it proposes fixes without executing them.")
            result["improvement_record"] = gov.record_audit(project, args.session, before)
        return result
    if args.command == "upgrade":
        return project.upgrade(args.session, args.task)
    if args.command == "adapter":
        state, events, _ = project.read(strict=True)
        return {"runtime": args.runtime, "agent": args.agent, "protocol_version": state.get("protocol_version", 1),
                "central_workflow": "MASTER_AGENT_WORKFLOW.md", "context": context_bundle(project.root, state, events),
                "startup_argv": ["uados", "--project", str(project.root), "session", "start", "--agent", args.agent, "--runtime", args.runtime],
                "instruction": "Read central workflow and .agent/startup_protocol.md when protocol2 is enabled. Inspect and acknowledge the issued Understanding Report before tracked work. Adapters supply instructions; they do not launch or authenticate the named product."}
    if args.command == "export":
        return project.export(args.path, args.include)
    if args.command == "session":
        if args.action == "start":
            return project.start_session(args.agent, args.runtime)
        if args.action == "refresh":
            return project.refresh_session(args.session_id)
        if args.action == "acknowledge":
            return project.acknowledge(args.session_id, args.report_hash)
        return project.close_session(args.session_id, args.summary, args.next, args.blocker, args.failed)
    if args.command == "task":
        if args.action == "add":
            return project.add_task(args.session, args.title, args.description, args.risk, args.scope, args.depends)
        if args.action == "claim":
            return project.claim_task(args.session, args.task_id, args.lease_minutes, args.takeover_reason)
        if args.action == "record":
            return project.record_task(args.session, args.task_id, args.summary, args.evidence)
        if args.action == "review":
            return project.review_task(args.session, args.task_id, args.stage, args.verdict, args.challenge, args.evidence)
        if args.action == "complete":
            return project.complete_task(args.session, args.task_id)
        if args.action == "plan":
            return gov.plan_task(project, args.session, args.task_id, args.implementation, args.validation, args.evidence)
        if args.action == "replan":
            return gov.replan_task(project, args.session, args.task_id, args.reason, args.description, args.scope)
        return project.block_task(args.session, args.task_id, args.reason)
    if args.command == "agent":
        return orch.register_agent(project, args.session, args.capability)
    if args.command == "roles":
        if args.action == "generate":
            return orch.create_roles(project, args.session, args.task_id, args.type)
        if args.action == "select":
            return orch.select_agents(project, args.role_plan_id)
        return orch.assign_role(project, args.session, args.role_plan_id, args.role, args.agent)
    if args.command == "debate":
        if args.action == "open":
            return orch.open_debate(project, args.session, args.task_id, args.roles, args.stage)
        if args.action == "analysis":
            return orch.submit_analysis(project, args.session, args.debate_id, args.solution, args.assumption, args.risk, args.alternative, args.evidence)
        if args.action == "advance":
            return orch.advance_debate(project, args.session, args.debate_id)
        if args.action == "challenge":
            return orch.submit_challenge(project, args.session, args.debate_id, args.target, args.failure, args.unsupported, args.alternative, args.missing_evidence, args.evidence)
        if args.action == "vote":
            return orch.vote(project, args.session, args.debate_id, args.select, args.verdict, args.reason, args.evidence)
        if args.action == "consensus":
            return orch.finalize(project, args.session, args.debate_id, args.select, args.reason, args.risk)
        return orch.packet(project, args.debate_id, args.agent)
    if args.command == "change":
        fields = ("problem", "background", "alternatives", "decision", "impact", "risk", "validation", "evidence")
        return gov.propose_change(project, args.session, args.task_id, *read_record(project, args.record, fields))
    if args.command == "note":
        return project.add_note(args.session, args.title, args.body, args.kind)
    if args.command == "decision":
        return project.add_decision(args.session, args.title, args.problem, args.alternatives, args.decision, args.reason, args.evidence, args.risk, args.task)
    if args.command == "experiment":
        if args.action == "add":
            try:
                command = json.loads(args.command_json)
            except ValueError as exc:
                raise UadosError("--command-json must contain valid JSON.") from exc
            return add_experiment(project, args.session, args.title, args.hypothesis, command, args.config, args.dataset, args.seed, args.scope, args.cwd, args.hypothesis_id)
        if args.action == "run":
            return run_experiment(project, args.session, args.experiment_id, args.timeout)
        if args.action == "resolve":
            return resolve_experiment(project, args.session, args.experiment_id, args.reason)
        return conclude_experiment(project, args.session, args.experiment_id, args.conclusion, args.evidence)
    if args.command == "research":
        if args.action == "source":
            return gov.add_source(project, args.session, *read_record(project, args.record, ("title", "identifier", "url", "claim", "limitation", "access", "evidence", "corpus")))
        if args.action == "idea":
            return gov.add_idea(project, args.session, *read_record(project, args.record, ("title", "fields", "sources", "evidence")))
        if args.action == "hypothesis":
            return gov.add_hypothesis(project, args.session, *read_record(project, args.record, ("idea", "prediction", "baseline", "metric", "rejection", "uncertainty", "evidence")))
        if args.action == "novelty":
            return gov.review_idea(project, args.session, args.idea_id, args.verdict, args.challenge, args.evidence)
        return gov.conclude_hypothesis(project, args.session, args.hypothesis_id, args.experiment, args.run, args.verdict, args.reason, args.evidence)
    if args.command == "improvement":
        return gov.add_improvement(project, args.session, *read_record(project, args.record, ("problem", "root_cause", "improvement", "implementation", "prevention", "evidence")))
    raise UadosError("Unsupported command.")


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result = dispatch(args)
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        if args.command == "audit" and not result["ok"]:
            return 1
        if args.command == "trust" and args.action == "verify" and not result["ok"]:
            return 1
        if args.command == "experiment" and args.action == "run" and result["status"] != "succeeded":
            return 1
        return 0
    except (UadosError, OSError, UnicodeError, sqlite3.DatabaseError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
