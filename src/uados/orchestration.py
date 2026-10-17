"""Deterministic role proposals and executable, evidence-bound adversarial debates."""

from .project import check_evidence, next_id, require_text, task_contributors
from .protocol import ensure_v2, spec
from .storage import UadosError, digest, evidence_files, now


def generate_roles(description, mode, task_type="auto"):
    text = description.lower()
    research = any(word in text for word in ("research", "hypothesis", "biosensor", "cellulose", "literature", "scientific", "experiment"))
    software = any(word in text for word in ("software", "database", "api", "application", "backend", "code", "runtime"))
    selected = task_type if task_type != "auto" else "hybrid" if research and software else "research" if research or mode == "research" else "software"
    roles = []
    def add(identifier, name, capability, reviewer, reason):
        roles.append({"id": identifier, "name": name, "capability": capability, "reviewer": reviewer, "reason": reason})
    if selected in {"software", "hybrid"}:
        add("architecture", "Architecture Agent", "architecture", True, "Challenge interfaces, state and maintainability")
        add("implementation", "Backend Engineer Agent" if any(w in text for w in ("database", "api", "backend")) else "Software Engineer Agent", "software", False, "Implement the accepted plan")
        if any(w in text for w in ("performance", "optimize", "latency", "database")):
            add("performance", "Performance Agent", "performance", True, "Challenge measurement and resource assumptions")
        add("security", "Security Agent", "security", True, "Challenge trust, input and data boundaries")
        add("testing", "Testing Agent", "testing", True, "Challenge validation and failure handling")
    if selected in {"research", "hybrid"}:
        add("principal-investigator", "Principal Investigator Agent", "research", False, "Define a falsifiable research question")
        add("literature-review", "Literature Review Agent", "literature", True, "Check existing work and source access")
        material = any(w in text for w in ("cellulose", "material", "biosensor", "bacterial"))
        add("materials-science" if material else "domain-specialist", "Materials Science Agent" if material else "Domain Specialist Agent", "materials" if material else "research", True, "Challenge domain assumptions")
        add("experimental-design", "Experimental Design Agent", "experimental-design", True, "Check controls, baselines and uncertainty")
        add("novelty-review", "Novelty Reviewer Agent", "novelty", True, "Try to falsify the claimed contribution")
        add("publication-review", "Publication Reviewer Agent", "publication", True, "Assess evidence, limitations and publication claims")
    if selected not in {"software", "research", "hybrid"}:
        raise UadosError("Task type must be auto, software, research or hybrid.")
    return {"task_type": selected, "method": "Deterministic declared rules, not an LLM or proof of expertise", "roles": roles}


def register_agent(project, session_id, capabilities):
    capabilities = sorted({require_text(value, "Capability") for value in capabilities})
    if not capabilities:
        raise UadosError("Declare at least one capability; declarations are not credentials.")
    def operation(state, events, session):
        ensure_v2(state)
        profile = {"id": session["agent"], "runtime": session.get("runtime", "other"), "capabilities": capabilities}
        state["agents"][session["agent"]] = profile
        return {"agent": profile}
    return project.mutate("agent.register", "Declared agent capabilities", operation, session_id)


def create_roles(project, session_id, task_id, task_type="auto"):
    def operation(state, events, session):
        ensure_v2(state)
        task = project._task(state, task_id)
        if session["agent"] != task["author"] and session["id"] != task.get("owner"):
            raise UadosError("Only the task author or owner may generate its active role plan.")
        if task["status"] == "done":
            raise UadosError("Completed task roles are historical; create a new task.")
        proposal = generate_roles(task["title"] + " " + task["description"], state["mode"], task_type)
        identifier = next_id(state, "RP")
        plan = dict(proposal, id=identifier, task=task_id, spec_fingerprint=digest(spec(task)), assignments={}, created_at=now())
        state["role_plans"][identifier] = plan
        task["role_plan"] = identifier
        return {"role_plan": plan}
    return project.mutate("roles.generate", "Generated roles for " + task_id, operation, session_id)


def _role_plan(state, identifier):
    if identifier not in state.get("role_plans", {}):
        raise UadosError("Unknown role plan: " + identifier)
    return state["role_plans"][identifier]


def assignment_snapshot(state, plan):
    return {"roles": plan["roles"], "assignments": plan["assignments"],
            "profiles": {name: state.get("agents", {}).get(name) for name in sorted(set(plan["assignments"].values()))}}


def select_agents(project, plan_id):
    state, _, _ = project.read(strict=True)
    plan = _role_plan(state, plan_id)
    task = project._task(state, plan["task"])
    result = {}
    for role in plan["roles"]:
        eligible = [name for name, profile in sorted(state.get("agents", {}).items()) if role["capability"] in profile["capabilities"] and (not role["reviewer"] or name not in task_contributors(task))]
        result[role["id"]] = eligible
    return {"role_plan": plan_id, "candidates": result, "dispatch": "Candidates only. Assign explicitly and dispatch the packet through the selected runtime."}


def assign_role(project, session_id, plan_id, role_id, agent):
    def operation(state, events, session):
        ensure_v2(state)
        plan = _role_plan(state, plan_id)
        task = project._task(state, plan["task"])
        if session["agent"] != task["author"] and session["id"] != task.get("owner"):
            raise UadosError("Only the task author or owner may assign its roles.")
        if any(d["role_plan"] == plan_id for d in state["debates"].values()):
            raise UadosError("Assignments are frozen after opening a debate. Generate a new role plan to reassign.")
        role = next((r for r in plan["roles"] if r["id"] == role_id), None)
        profile = state["agents"].get(agent)
        if role is None or profile is None or role["capability"] not in profile["capabilities"]:
            raise UadosError("The role needs a registered agent with its declared capability.")
        if role["reviewer"] and agent in task_contributors(task):
            raise UadosError("Independent review roles exclude task authors and all implementation contributors.")
        plan["assignments"][role_id] = agent
        return {"role_plan": plan_id, "role": role_id, "agent": agent}
    return project.mutate("roles.assign", "Assigned " + role_id, operation, session_id)


def plan_binding(project, state, debate):
    task = project._task(state, debate["task"])
    roles = _role_plan(state, debate["role_plan"])
    return digest({"task": project.task_fingerprint(task, debate["stage"]), "selection": assignment_snapshot(state, roles)})


def validate_debate(project, state, debate):
    plan = _role_plan(state, debate["role_plan"])
    for role in plan["roles"]:
        profile = state.get("agents", {}).get(plan["assignments"].get(role["id"]), {})
        if role["capability"] not in profile.get("capabilities", []):
            raise UadosError("Role selection is stale or unsupported: " + role["id"])
    if plan_binding(project, state, debate) != debate["binding"]:
        raise UadosError("Debate is stale: task, code, policy, assignment or capability profile changed. Open a new debate.")
    from .protocol import all_evidence
    evidence = []
    for name in ("analyses", "challenges", "votes"):
        for entry in debate[name]:
            evidence.extend(entry["evidence"])
    problems = check_evidence(project.root, evidence)
    if problems:
        raise UadosError("Debate evidence changed: " + "; ".join(problems))


def participants(state, debate):
    return set(_role_plan(state, debate["role_plan"])["assignments"].values())


def eligible_reviewers(state, task, plan):
    return {plan["assignments"][r["id"]] for r in plan["roles"] if r["reviewer"]} - task_contributors(task)


def open_debate(project, session_id, task_id, role_plan_id, stage):
    if stage not in {"plan", "result"}:
        raise UadosError("Debate stage must be plan or result.")
    def operation(state, events, session):
        ensure_v2(state)
        task = project._task(state, task_id)
        plan = _role_plan(state, role_plan_id)
        if plan["task"] != task_id or plan["spec_fingerprint"] != digest(spec(task)):
            raise UadosError("Role plan does not match the current task specification.")
        if set(plan["assignments"]) != {r["id"] for r in plan["roles"]}:
            raise UadosError("Assign every generated role before debate.")
        if len(eligible_reviewers(state, task, plan)) < 2:
            raise UadosError("Major debate requires at least two independent review identities, regardless of role count.")
        if not task.get("plan"):
            raise UadosError("Record the task implementation/validation plan first.")
        if task["risk"] == "major":
            from .governance import current_change
            current_change(project, state, task)
        for role in plan["roles"]:
            profile = state["agents"].get(plan["assignments"][role["id"]], {})
            if role["capability"] not in profile.get("capabilities", []):
                raise UadosError("An assigned agent no longer declares its required capability.")
        for previous in state["debates"].values():
            if previous["task"] == task_id and previous["stage"] == stage and previous.get("task_revision") == task["revision"]:
                ballots = {v["agent"]: v for v in previous["votes"]}
                if any(v["verdict"] == "request_changes" for v in ballots.values()):
                    raise UadosError("Resolve the previous dissent in its debate, or explicitly replan with a recorded reason before opening another.")
        if stage == "plan" and task["status"] not in {"pending", "blocked"}:
            raise UadosError("Plan debate must precede execution.")
        if stage == "result" and (task["status"] != "in_progress" or not task["evidence"]):
            raise UadosError("Result debate requires submitted active work.")
        if stage == "result":
            from .storage import scope_snapshot
            if scope_snapshot(project.root, task["scope"]) != task["submission_files"]:
                raise UadosError("Scoped files changed after submission; record current work before result debate.")
        identifier = next_id(state, "D")
        debate = {"id": identifier, "task": task_id, "stage": stage, "role_plan": role_plan_id,
                  "round": "analysis", "analyses": [], "challenges": [], "votes": [], "consensus": None,
                  "created_at": now(), "opened_by": session["agent"], "task_revision": task["revision"]}
        debate["binding"] = plan_binding(project, state, debate)
        state["debates"][identifier] = debate
        return {"debate": identifier, "round": "analysis", "binding": debate["binding"]}
    return project.mutate("debate.open", "Opened " + stage + " debate for " + task_id, operation, session_id)


def _debate(state, identifier):
    if identifier not in state.get("debates", {}):
        raise UadosError("Unknown debate: " + identifier)
    return state["debates"][identifier]


def submit_analysis(project, session_id, debate_id, solution, assumptions, risks, alternatives, evidence):
    for value, label in ((solution, "Solution"),):
        require_text(value, label)
    if not assumptions or not risks or not alternatives or not evidence:
        raise UadosError("Analysis requires solution, assumptions, risks, alternatives and evidence.")
    for value in list(assumptions) + list(risks) + list(alternatives):
        require_text(value, "Analysis assumption/risk/alternative")
    def operation(state, events, session):
        debate = _debate(state, debate_id)
        validate_debate(project, state, debate)
        if debate["round"] != "analysis" or session["agent"] not in participants(state, debate):
            raise UadosError("Only assigned participants may analyze during round1.")
        if any(a["agent"] == session["agent"] for a in debate["analyses"]):
            raise UadosError("Independent analysis already submitted; it is immutable.")
        analysis_id = "%s-A%03d" % (debate_id, len(debate["analyses"]) + 1)
        debate["analyses"].append({"id": analysis_id, "agent": session["agent"], "session": session_id, "solution": solution,
                                    "assumptions": list(assumptions), "risks": list(risks), "alternatives": list(alternatives),
                                    "evidence": evidence_files(project.root, evidence), "at": now()})
        return {"analysis": analysis_id}
    return project.mutate("debate.analysis", "Independent analysis for " + debate_id, operation, session_id)


def advance_debate(project, session_id, debate_id):
    def operation(state, events, session):
        debate = _debate(state, debate_id)
        validate_debate(project, state, debate)
        people = participants(state, debate)
        if session["agent"] not in people:
            raise UadosError("Only debate participants may advance rounds.")
        if debate["round"] == "analysis" and {a["agent"] for a in debate["analyses"]} == people:
            debate["round"] = "challenge"
        elif debate["round"] == "challenge" and {a["agent"] for a in debate["challenges"]} == people:
            debate["round"] = "vote"
        else:
            raise UadosError("Every assigned participant must complete the current round before advancing.")
        return {"debate": debate_id, "round": debate["round"]}
    return project.mutate("debate.advance", "Advanced " + debate_id, operation, session_id)


def submit_challenge(project, session_id, debate_id, target, failure, unsupported, alternative, missing, evidence):
    for value in (failure, unsupported, alternative, missing):
        require_text(value, "Adversarial challenge field")
    if not evidence:
        raise UadosError("Challenge requires evidence.")
    def operation(state, events, session):
        debate = _debate(state, debate_id)
        validate_debate(project, state, debate)
        analysis = next((a for a in debate["analyses"] if a["id"] == target), None)
        if debate["round"] != "challenge" or session["agent"] not in participants(state, debate):
            raise UadosError("Challenge belongs to an assigned participant in round2.")
        if analysis is None or analysis["agent"] == session["agent"]:
            raise UadosError("Challenge another participant's recorded analysis.")
        if any(c["agent"] == session["agent"] for c in debate["challenges"]):
            raise UadosError("Challenge already submitted; retain it and open a new debate for rework.")
        debate["challenges"].append({"agent": session["agent"], "target": target, "failure": failure, "unsupported": unsupported,
                                      "alternative": alternative, "missing_evidence": missing, "evidence": evidence_files(project.root, evidence), "at": now()})
        return {"debate": debate_id, "challenger": session["agent"]}
    return project.mutate("debate.challenge", "Adversarial challenge for " + debate_id, operation, session_id)


def vote(project, session_id, debate_id, selected, verdict, reason, evidence):
    reason = require_text(reason, "Vote rationale and challenge resolution")
    if verdict not in {"approve", "request_changes"} or not evidence:
        raise UadosError("Vote requires approve/request_changes and evidence.")
    def operation(state, events, session):
        debate = _debate(state, debate_id)
        validate_debate(project, state, debate)
        if debate["round"] != "vote" or session["agent"] not in participants(state, debate):
            raise UadosError("Voting is available after every participant's analysis and challenge.")
        if selected not in {a["id"] for a in debate["analyses"]}:
            raise UadosError("Select an actual recorded analysis, not a new unreviewed approach.")
        debate["votes"].append({"agent": session["agent"], "session": session_id, "selected": selected, "verdict": verdict,
                                "reason": reason, "evidence": evidence_files(project.root, evidence), "at": now()})
        task = project._task(state, debate["task"])
        if verdict == "request_changes" and session["agent"] in eligible_reviewers(state, task, _role_plan(state, debate["role_plan"])):
            task["reviews"].append({"agent": session["agent"], "session": session_id, "stage": debate["stage"], "verdict": verdict, "challenge": reason, "evidence": evidence_files(project.root, evidence), "at": now(), "fingerprint": project.task_fingerprint(task, debate["stage"]), "debate": debate_id})
        return {"debate": debate_id, "verdict": verdict}
    return project.mutate("debate.vote", "Recorded vote for " + debate_id, operation, session_id)


def finalize(project, session_id, debate_id, selected, reasoning, risks):
    require_text(reasoning, "Consensus reasoning")
    if not risks:
        raise UadosError("Consensus must preserve remaining risks.")
    def operation(state, events, session):
        debate = _debate(state, debate_id)
        validate_debate(project, state, debate)
        if debate["round"] != "vote" or session["agent"] not in participants(state, debate):
            raise UadosError("Consensus requires the completed three-round participant process.")
        latest = {v["agent"]: v for v in debate["votes"]}
        if set(latest) != participants(state, debate):
            raise UadosError("Every assigned participant must vote before consensus.")
        if any(v["verdict"] != "approve" or v["selected"] != selected for v in latest.values()):
            raise UadosError("Unresolved dissent or different selected approaches prevent consensus. Keep objections and resolve them explicitly.")
        task = project._task(state, debate["task"])
        reviewers = eligible_reviewers(state, task, _role_plan(state, debate["role_plan"]))
        if len(reviewers) < 2:
            raise UadosError("Consensus needs two independent reviewers.")
        chosen = next((a for a in debate["analyses"] if a["id"] == selected), None)
        if chosen is None:
            raise UadosError("Unknown selected analysis.")
        if debate["stage"] == "plan" and task["risk"] == "major":
            from .governance import current_change
            change = current_change(project, state, task)
            change.update(status="approved", consensus=debate_id)
        fingerprint = project.task_fingerprint(task, debate["stage"])
        for reviewer in sorted(reviewers):
            ballot = latest[reviewer]
            task["reviews"].append({"agent": reviewer, "session": ballot["session"], "stage": debate["stage"], "verdict": "approve", "challenge": ballot["reason"], "evidence": ballot["evidence"], "at": now(), "fingerprint": fingerprint, "debate": debate_id})
        debate.update(round="consensus", consensus={"selected_analysis": selected, "selected_approach": chosen["solution"],
                      "rejected_alternatives": [a["solution"] for a in debate["analyses"] if a["id"] != selected] + chosen["alternatives"],
                      "reasoning": reasoning, "remaining_risks": list(risks), "reviewers": sorted(reviewers), "task_fingerprint": fingerprint, "at": now()})
        return {"debate": debate_id, "consensus": debate["consensus"]}
    return project.mutate("debate.consensus", "Reached consensus for " + debate_id, operation, session_id)


def require_consensus(project, state, task, stage):
    candidates = [d for d in state.get("debates", {}).values() if d["task"] == task["id"] and d["stage"] == stage and d.get("consensus") and d["role_plan"] == task.get("role_plan")]
    for debate in reversed(candidates):
        try:
            validate_debate(project, state, debate)
            people = eligible_reviewers(state, task, _role_plan(state, debate["role_plan"]))
            if len(people) >= 2 and set(debate["consensus"]["reviewers"]).issubset(people):
                return debate
        except UadosError:
            continue
    raise UadosError("Protocol2 major work requires current three-round %s consensus from two independent reviewers." % stage)


def packet(project, debate_id, agent):
    state, events, _ = project.read(strict=True)
    debate = _debate(state, debate_id)
    if agent not in participants(state, debate):
        raise UadosError("Agent is not assigned to this debate.")
    from .context import context_bundle
    visible = dict(debate)
    if debate["round"] == "analysis":
        visible["analyses"] = [a for a in debate["analyses"] if a["agent"] == agent]
    return {"agent": state["agents"][agent], "roles": [r for r in _role_plan(state, debate["role_plan"])["roles"] if _role_plan(state, debate["role_plan"])["assignments"][r["id"]] == agent],
            "task": project._task(state, debate["task"]), "debate": visible, "context": context_bundle(project.root, state, events),
            "instruction": "Read MASTER_AGENT_WORKFLOW and .agent protocols. Independently analyze, then challenge another analysis, then vote using recorded evidence. This packet does not launch or authenticate a model; local ledger files remain visible."}
