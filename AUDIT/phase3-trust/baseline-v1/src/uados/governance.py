"""Change control, evidence-based research records, and proposed improvements."""

from urllib.parse import urlsplit

from .project import check_evidence, next_id, require_text
from .protocol import ensure_v2, spec
from .storage import UadosError, digest, evidence_files, now


def checked(project, records):
    problems = check_evidence(project.root, records)
    if problems:
        raise UadosError("; ".join(problems))


def plan_task(project, session_id, task_id, implementation, validation, evidence):
    require_text(implementation, "Implementation plan")
    require_text(validation, "Validation plan")
    if not evidence:
        raise UadosError("Task plan requires a maintained evidence artifact.")
    def operation(state, events, session):
        task = project._task(state, task_id)
        if task["status"] not in {"pending", "blocked"} or session["agent"] != task["author"]:
            raise UadosError("Only the author may plan pending/blocked work; use task replan before revising active work.")
        if task.get("plan") and any(d["task"] == task_id and any(v["verdict"] == "request_changes" for v in d["votes"]) for d in state.get("debates", {}).values()):
            raise UadosError("Retain dissent and use explicit task replan with a resolution reason before replacing the plan.")
        task.update(plan={"implementation": implementation, "validation": validation, "evidence": evidence_files(project.root, evidence), "at": now()}, revision=task["revision"] + 1)
        return {"task": task_id, "revision": task["revision"]}
    return project.mutate("task.plan", "Planned " + task_id, operation, session_id)


def replan_task(project, session_id, task_id, reason, description=None, scopes=None):
    require_text(reason, "Replanning reason, changed assumptions and dissent disposition")
    def operation(state, events, session):
        task = project._task(state, task_id)
        if task["status"] == "done" or (session["agent"] != task["author"] and task.get("owner") != session_id):
            raise UadosError("Only the author or owner may replan unfinished work.")
        if task.get("owner") and task["owner"] != session_id:
            from datetime import datetime, timezone
            if datetime.fromisoformat(task["lease_until"]) > datetime.now(timezone.utc):
                raise UadosError("Replanning cannot revoke another active lease; the owner must hand over or replan first.")
        if description is not None:
            task["description"] = require_text(description, "Description")
        if scopes is not None:
            from .storage import scope_snapshot
            if task["risk"] == "major" and not scopes:
                raise UadosError("Major work requires explicit scope.")
            scope_snapshot(project.root, scopes)
            task["scope"] = list(scopes)
        task["work"].append({"kind": "replan", "summary": reason, "at": now(), "agent": session["agent"]})
        task.update(status="pending", owner=None, lease_until=None, plan=None, change=None, change_snapshot=None, role_plan=None, submission_files=None, revision=task["revision"] + 1)
        return {"task": task_id, "status": "pending", "instruction": "Record a new plan/change and new debate; prior objections remain in history."}
    return project.mutate("task.replan", reason, operation, session_id)


def propose_change(project, session_id, task_id, problem, background, alternatives, decision, impact, risk, validation, evidence):
    for value in (problem, background, decision, impact, risk, validation):
        require_text(value, "Change request field")
    if len(alternatives) < 2 or not evidence:
        raise UadosError("Change requests need at least two alternatives and evidence.")
    for value in alternatives:
        require_text(value, "Change alternative")
    def operation(state, events, session):
        ensure_v2(state)
        task = project._task(state, task_id)
        if task["risk"] != "major" or task["status"] not in {"pending", "blocked"} or session["agent"] != task["author"]:
            raise UadosError("Change requests precede a major task and are proposed by its author.")
        if not task.get("plan"):
            raise UadosError("Record the implementation/validation plan before proposing its change.")
        identifier = next_id(state, "CR")
        change = {"id": identifier, "task": task_id, "problem": problem, "background": background,
                  "alternatives": list(alternatives), "decision": decision, "impact": impact, "risk": risk,
                  "validation": validation, "evidence": evidence_files(project.root, evidence), "status": "proposed",
                  "spec_fingerprint": digest(spec(task)), "plan_fingerprint": digest(task["plan"]), "agent": session["agent"], "at": now()}
        state["changes"][identifier] = change
        task["change"] = identifier
        task["change_snapshot"] = {k: v for k, v in change.items() if k not in {"status", "consensus"}}
        return {"change": identifier, "status": "proposed"}
    return project.mutate("change.propose", problem, operation, session_id)


def current_change(project, state, task):
    change = state.get("changes", {}).get(task.get("change"))
    if not change or change["spec_fingerprint"] != digest(spec(task)) or change["plan_fingerprint"] != digest(task.get("plan")):
        raise UadosError("Major protocol2 work requires a change request matching its current plan/specification.")
    if task.get("change_snapshot") != {k: v for k, v in change.items() if k not in {"status", "consensus"}}:
        raise UadosError("Change request differs from its reviewed task snapshot.")
    checked(project, change["evidence"])
    return change


def add_source(project, session_id, title, identifier, url, claim, limitation, access, evidence, corpus):
    for value in (title, identifier, claim, limitation, corpus):
        require_text(value, "Literature field")
    if access not in {"full_text", "abstract", "unavailable"} or not evidence:
        raise UadosError("Literature requires truthful access scope and an evidence manifest.")
    if urlsplit(url).scheme not in {"https", "http"}:
        raise UadosError("Use a stable HTTP(S) primary-source URL; adding it does not fetch it.")
    normalized = identifier.strip().casefold()
    normalized_url = url.split("#")[0].rstrip("/").casefold()
    def operation(state, events, session):
        ensure_v2(state)
        if any(s["identifier"].casefold() == normalized or s["url"].split("#")[0].rstrip("/").casefold() == normalized_url for s in state["literature"].values()):
            raise UadosError("Duplicate source identifier or URL cannot inflate coverage. Use a distinct source or preserve a new explicit version outside this registry.")
        source_id = next_id(state, "L")
        state["literature"][source_id] = {"id": source_id, "title": title, "identifier": identifier.strip(), "url": url,
              "claim": claim, "limitation": limitation, "access": access, "corpus": corpus,
              "evidence": evidence_files(project.root, evidence), "agent": session["agent"], "accessed_at": now()}
        return {"source": source_id, "access": access}
    return project.mutate("research.source", title, operation, session_id)


IDEA_FIELDS = ("existing_work", "current_limitation", "scientific_gap", "proposed_innovation", "prior_methods_insufficient", "expected_contribution", "publication_potential", "coverage_limit")


def idea_fingerprint(project, state, idea):
    sources = []
    for identifier in idea["sources"]:
        source = state["literature"].get(identifier)
        if source is None:
            raise UadosError("Idea references an unknown literature source: " + identifier)
        checked(project, source["evidence"])
        sources.append(source)
    checked(project, idea["evidence"])
    from .context import maintained_context
    from .storage import GENERATED_PATHS
    policies = {path: text for path, text in maintained_context(project.root).items() if path.startswith("RESEARCH_MANAGEMENT/") and path not in GENERATED_PATHS}
    return digest({"idea": {key: idea[key] for key in ("title", "sources", "fields", "evidence")}, "sources": sources, "research_policies": policies})


def add_idea(project, session_id, title, fields, sources, evidence):
    require_text(title, "Research idea")
    for name in IDEA_FIELDS:
        require_text(fields.get(name), "Research idea " + name)
    if not sources or not evidence:
        raise UadosError("Research ideas require source IDs and coverage/analysis evidence.")
    def operation(state, events, session):
        ensure_v2(state)
        identifier = next_id(state, "IDEA")
        idea = {"id": identifier, "title": title, "fields": fields, "sources": sorted(set(sources)),
                "evidence": evidence_files(project.root, evidence), "agent": session["agent"], "created_at": now(), "reviews": []}
        idea_fingerprint(project, state, idea)
        state["ideas"][identifier] = idea
        return {"idea": identifier}
    return project.mutate("research.idea", title, operation, session_id)


def review_idea(project, session_id, idea_id, verdict, challenge, evidence):
    require_text(challenge, "Peer-review challenge and contribution judgment")
    if verdict not in {"candidate", "overlap", "inconclusive"} or not evidence:
        raise UadosError("Novelty review requires candidate/overlap/inconclusive and evidence.")
    def operation(state, events, session):
        ensure_v2(state)
        idea = state["ideas"].get(idea_id)
        if not idea:
            raise UadosError("Unknown research idea: " + idea_id)
        if session["agent"] == idea["agent"]:
            raise UadosError("The idea author cannot provide its independent novelty review.")
        fingerprint = idea_fingerprint(project, state, idea)
        if verdict == "candidate":
            sources = [state["literature"][identifier] for identifier in idea["sources"]]
            if len(sources) < 2 or any(source["access"] != "full_text" for source in sources) or len({s["corpus"].strip().casefold() for s in sources}) < 2:
                raise UadosError("Candidate novelty requires at least two distinct accessed full-text corpora, no unavailable/abstract-only support, and explicit coverage evidence. It is still provisional.")
        review = {"agent": session["agent"], "verdict": verdict, "challenge": challenge, "fingerprint": fingerprint,
                  "evidence": evidence_files(project.root, evidence), "at": now(), "meaning": "Candidate is provisional within the reviewed corpus, not global novelty or publication acceptance."}
        idea["reviews"].append(review)
        return {"idea": idea_id, "review": review}
    return project.mutate("research.novelty", "Novelty review of " + idea_id, operation, session_id)


def add_hypothesis(project, session_id, idea_id, prediction, baseline, metric, rejection, uncertainty, evidence):
    for value in (prediction, baseline, metric, rejection, uncertainty):
        require_text(value, "Hypothesis protocol field")
    if not evidence:
        raise UadosError("Hypothesis requires experimental-design evidence.")
    def operation(state, events, session):
        ensure_v2(state)
        idea = state["ideas"].get(idea_id)
        if not idea:
            raise UadosError("Hypothesis must reference an existing research idea.")
        identifier = next_id(state, "H")
        state["hypotheses"][identifier] = {"id": identifier, "idea": idea_id, "idea_fingerprint": idea_fingerprint(project, state, idea),
             "prediction": prediction, "baseline": baseline, "metric": metric, "rejection_criterion": rejection,
             "uncertainty": uncertainty, "evidence": evidence_files(project.root, evidence), "agent": session["agent"], "created_at": now(), "outcomes": []}
        return {"hypothesis": identifier}
    return project.mutate("research.hypothesis", prediction, operation, session_id)


def conclude_hypothesis(project, session_id, hypothesis_id, experiment_id, run_id, verdict, reason, evidence):
    require_text(reason, "Hypothesis interpretation with uncertainty")
    if verdict not in {"supported", "refuted", "inconclusive"} or not evidence:
        raise UadosError("Hypothesis outcome needs a valid verdict and analysis evidence.")
    def operation(state, events, session):
        ensure_v2(state)
        hypothesis = state["hypotheses"].get(hypothesis_id)
        experiment = state["experiments"].get(experiment_id)
        if not hypothesis or not experiment or experiment.get("hypothesis_id") != hypothesis_id:
            raise UadosError("Use the exact experiment linked to this hypothesis.")
        from .research import validate_hypothesis
        validate_hypothesis(project, state, experiment)
        run = next((r for r in experiment["runs"] if r["id"] == run_id), None)
        if run is None or run["status"] == "running":
            raise UadosError("Use an exact resolved experiment/run pair.")
        checked(project, run.get("outputs", []))
        if verdict != "inconclusive" and run["status"] != "succeeded":
            raise UadosError("Failed, interrupted or invalidated execution cannot be a scientific supported/refuted finding.")
        hypothesis["outcomes"].append({"experiment": experiment_id, "run": run_id, "run_fingerprint": run["fingerprint"],
               "operational_status": run["status"], "verdict": verdict, "reason": reason,
               "evidence": evidence_files(project.root, evidence), "agent": session["agent"], "at": now()})
        return {"hypothesis": hypothesis_id, "experiment": experiment_id, "run": run_id, "verdict": verdict}
    return project.mutate("research.outcome", reason, operation, session_id)


def add_improvement(project, session_id, problem, root_cause, improvement, implementation, prevention, evidence, task_id=None):
    for value in (problem, root_cause, improvement, implementation, prevention):
        require_text(value, "Improvement record field")
    if not evidence:
        raise UadosError("Improvement requires diagnostic/validation evidence.")
    def operation(state, events, session):
        ensure_v2(state)
        if task_id:
            project._task(state, task_id)
        identifier = next_id(state, "IMP")
        state["improvements"][identifier] = {"id": identifier, "problem": problem, "root_cause": root_cause,
              "improvement": improvement, "implementation": implementation, "future_prevention": prevention,
              "evidence": evidence_files(project.root, evidence), "task": task_id, "agent": session["agent"], "at": now(), "status": "recorded"}
        return {"improvement": identifier}
    return project.mutate("improvement.add", problem, operation, session_id)


def audit_candidates(audit):
    findings = audit.get("errors", []) + ["Projection drift: " + p for p in audit.get("projection_drift", [])]
    findings += [w for w in audit.get("warnings", []) if not w.startswith("Completed task scope has changed")]
    return [{"problem": problem, "fingerprint": digest(problem), "root_cause": "Undetermined; investigate the recorded condition before assigning cause.",
             "improvement": "Restore missing evidence or context, resolve ownership/run state, or add a bounded workflow rule after review.",
             "implementation": "Proposed only; no source modification or automated remediation.",
             "future_prevention": "Preserve a reproducer and validate an owned change before marking the finding resolved."} for problem in sorted(set(findings))]


def record_audit(project, session_id, audit):
    candidates = audit_candidates(audit)
    if not candidates:
        return {"recorded": [], "note": "No actionable improvement candidates; no event was appended."}
    def operation(state, events, _):
        ensure_v2(state)
        session = project._session(state, events, session_id, current=False, acknowledged=True)
        recorded = []
        for candidate in candidates:
            if any(item.get("finding_fingerprint") == candidate["fingerprint"] for item in state["improvements"].values()):
                continue
            identifier = next_id(state, "IMP")
            state["improvements"][identifier] = dict(candidate, id=identifier, finding_fingerprint=candidate["fingerprint"], status="proposed", agent=session["agent"], at=now(), audit_head=audit["head_hash"], evidence=[])
            recorded.append(identifier)
        return {"recorded": recorded, "_no_event": not recorded}
    # Diagnostic logging may use an acknowledged but stale session; it authorizes no work.
    return project.mutate("audit.findings", "Recorded proposed audit improvements", operation, session_id, gate=False, advance=False)
