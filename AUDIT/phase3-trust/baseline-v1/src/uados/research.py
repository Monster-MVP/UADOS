"""Explicit experiment execution with intent, immutable run outputs and recovery."""

import importlib.metadata
import json
import os
import platform
import signal
import subprocess
import sys
import time

from .project import require_text
from .storage import UadosError, digest, evidence_files, now, safe_path, scope_snapshot


def add_experiment(project, session_id, title, hypothesis, command, config, datasets, seed, scopes, cwd=".", hypothesis_id=None):
    title, hypothesis = require_text(title, "Title"), require_text(hypothesis, "Hypothesis and evaluation plan")
    if not isinstance(command, list) or not command or not all(isinstance(arg, str) and arg for arg in command):
        raise UadosError("Command must be a nonempty JSON array of string arguments.")
    if not scopes:
        raise UadosError("Experiments need code scope paths for provenance.")
    working_directory = safe_path(project.root, cwd)
    if not working_directory.is_dir():
        raise UadosError("Experiment working directory must be a directory.")
    scope_snapshot(project.root, scopes)
    from .project import next_id

    def operation(state, events, session):
        linked = state.get("hypotheses", {}).get(hypothesis_id) if hypothesis_id else None
        if hypothesis_id and not linked:
            raise UadosError("Unknown registered hypothesis: " + hypothesis_id)
        if linked:
            from .governance import checked, idea_fingerprint
            checked(project, linked["evidence"])
            if linked["idea_fingerprint"] != idea_fingerprint(project, state, state["ideas"][linked["idea"]]):
                raise UadosError("Hypothesis idea/source evidence changed; register a revised hypothesis.")
        experiment_id = next_id(state, "E")
        state["experiments"][experiment_id] = {
            "id": experiment_id, "title": title, "hypothesis": hypothesis,
            "command": command, "config": evidence_files(project.root, [config])[0],
            "datasets": evidence_files(project.root, datasets), "seed": seed,
            "scope": list(scopes), "cwd": working_directory.relative_to(project.root).as_posix(),
            "agent": session["agent"], "created_at": now(), "runs": [],
        }
        if linked:
            state["experiments"][experiment_id].update(hypothesis_id=hypothesis_id, hypothesis_snapshot=linked.copy())
        return {"experiment": experiment_id, "status": "planned"}
    return project.mutate("experiment.add", title, operation, session_id)


def hypothesis_design(hypothesis):
    return {key: value for key, value in hypothesis.items() if key != "outcomes"}


def validate_hypothesis(project, state, experiment):
    """Revalidate the registered scientific question, excluding appended outcomes."""
    if not experiment.get("hypothesis_id"):
        return None
    from .governance import checked, idea_fingerprint
    linked = state.get("hypotheses", {}).get(experiment["hypothesis_id"])
    if not linked or hypothesis_design(linked) != hypothesis_design(experiment["hypothesis_snapshot"]):
        raise UadosError("Registered hypothesis changed; register a revised experiment.")
    checked(project, linked["evidence"])
    idea = state.get("ideas", {}).get(linked["idea"])
    if not idea or linked["idea_fingerprint"] != idea_fingerprint(project, state, idea):
        raise UadosError("Hypothesis idea/source evidence changed; register a revised hypothesis.")
    return hypothesis_design(linked)


def provenance(project, experiment, state=None):
    from .project import check_evidence

    problems = check_evidence(project.root, [experiment["config"]] + experiment["datasets"])
    if problems:
        raise UadosError("Experiment inputs changed; register a new experiment: " + "; ".join(problems))
    files = scope_snapshot(project.root, experiment["scope"])
    if not files or any(value == "missing" for value in files.values()):
        raise UadosError("Experiment code scope is unavailable or empty.")
    try:
        commit = subprocess.run(["git", "-C", str(project.root), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5)
        git_head = commit.stdout.strip() if commit.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        git_head = None
    packages = sorted({(dist.metadata.get("Name", "unknown"), dist.version) for dist in importlib.metadata.distributions()})
    result = {"command": experiment["command"], "cwd": experiment["cwd"], "seed": experiment["seed"],
            "config": experiment["config"], "datasets": experiment["datasets"], "code_files": files,
            "git_head": git_head, "python": sys.version, "executable": sys.executable,
            "platform": platform.platform(), "packages": packages,
            "environment": {key: os.environ[key] for key in ("PYTHONHASHSEED", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "CUDA_VISIBLE_DEVICES") if key in os.environ},
            "runtime_note": "Versions describe the UADOS launcher environment. Commands using another interpreter/container must also emit their runtime metadata. Seed is recorded; the command must apply it."}
    if experiment.get("hypothesis_id"):
        if state is None:
            raise UadosError("Linked experiment provenance requires current ledger state.")
        result["hypothesis_design"] = validate_hypothesis(project, state, experiment)
    return result


def _terminate(process):
    if process.poll() is None:
        if os.name == "posix":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            process.kill()
        process.wait()


def run_experiment(project, session_id, experiment_id, timeout=3600):
    if timeout <= 0:
        raise UadosError("Experiment timeout must be positive.")
    holder = {}

    def begin(state, events, session):
        experiment = state["experiments"].get(experiment_id)
        if experiment is None:
            raise UadosError("Unknown experiment: " + experiment_id)
        if any(run["status"] == "running" for run in experiment["runs"]):
            raise UadosError("An unresolved run exists; inspect it and use experiment resolve before retrying.")
        metadata = provenance(project, experiment, state)
        run_id = "R%06d" % (len(experiment["runs"]) + 1)
        base = ".uados/runs/%s/%s" % (experiment_id, run_id)
        run = {"id": run_id, "status": "running", "started_at": now(), "session": session_id,
               "provenance": metadata, "fingerprint": digest(metadata), "stdout": base + "/stdout.txt",
               "stderr": base + "/stderr.txt", "timeout_seconds": timeout}
        experiment["runs"].append(run)
        holder.update(experiment=experiment, run=run)
        return {"experiment": experiment_id, "run": run_id, "status": "running"}
    project.mutate("experiment.start", "Started " + experiment_id, begin, session_id)
    experiment, run = holder["experiment"], holder["run"]
    stdout_path = safe_path(project.root, run["stdout"], allow_missing=True)
    stderr_path = safe_path(project.root, run["stderr"], allow_missing=True)
    stdout_path.parent.mkdir(parents=True, exist_ok=False)
    status, returncode, error, process = "failed", None, None, None
    started = time.monotonic()
    try:
        with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
            process = subprocess.Popen(experiment["command"], cwd=str(safe_path(project.root, experiment["cwd"])), stdout=stdout, stderr=stderr, start_new_session=os.name == "posix")
            try:
                returncode = process.wait(timeout=timeout)
                status = "succeeded" if returncode == 0 else "failed"
            except subprocess.TimeoutExpired:
                _terminate(process)
                returncode, status, error = process.returncode, "timed_out", "Run exceeded timeout."
            except KeyboardInterrupt:
                _terminate(process)
                returncode, status, error = process.returncode, "interrupted", "Launcher interrupted."
    except OSError as exc:
        error = str(exc)
    # Completion is durable even if another agent changed context while the process ran.
    # This finalizer cannot create new work; it only resolves the intent we already wrote.
    def finish(state, events, _):
        stored = state["experiments"][experiment_id]["runs"][-1]
        if stored["id"] != run["id"] or stored["status"] != "running":
            raise UadosError("Run was resolved by another session; inspect output before proceeding.")
        changed = scope_snapshot(project.root, experiment["scope"]) != run["provenance"]["code_files"]
        from .project import check_evidence
        input_changes = check_evidence(project.root, [experiment["config"]] + experiment["datasets"])
        try:
            validate_hypothesis(project, state, experiment)
        except UadosError as exc:
            input_changes.append("Hypothesis evidence changed during run: " + str(exc))
        final_status = "invalidated" if status == "succeeded" and (changed or input_changes) else status
        stored.update(status=final_status, ended_at=now(), returncode=returncode, error=error,
                      duration_seconds=round(time.monotonic() - started, 6), code_changed_during_run=changed,
                      input_changes=input_changes, outputs=evidence_files(project.root, [run["stdout"], run["stderr"]]))
        return {"experiment": experiment_id, "run": run["id"], "status": final_status, "returncode": returncode,
                "stdout": run["stdout"], "stderr": run["stderr"], "error": error}
    return project.mutate("experiment.finish", "Finished %s / %s" % (experiment_id, run["id"]), finish, session_id, gate=False, advance=False)


def resolve_experiment(project, session_id, experiment_id, reason):
    reason = require_text(reason, "Recovery evidence and reason")
    def operation(state, events, session):
        experiment = state["experiments"].get(experiment_id)
        if experiment is None:
            raise UadosError("Unknown experiment: " + experiment_id)
        unresolved = [run for run in experiment["runs"] if run["status"] == "running"]
        if not unresolved:
            raise UadosError("No unresolved experiment run exists.")
        for run in unresolved:
            run.update(status="interrupted", ended_at=now(), recovery_reason=reason)
            paths = [p for p in (run["stdout"], run["stderr"]) if safe_path(project.root, p, allow_missing=True).is_file()]
            run["outputs"] = evidence_files(project.root, paths)
        return {"experiment": experiment_id, "resolved": [run["id"] for run in unresolved], "status": "interrupted"}
    return project.mutate("experiment.resolve", reason, operation, session_id)


def conclude_experiment(project, session_id, experiment_id, conclusion, evidence):
    conclusion = require_text(conclusion, "Scientific interpretation including uncertainty")
    if not evidence:
        raise UadosError("Scientific conclusions require analysis evidence files.")
    def operation(state, events, session):
        experiment = state["experiments"].get(experiment_id)
        if experiment is None or not experiment["runs"]:
            raise UadosError("A recorded experiment run is required.")
        run = experiment["runs"][-1]
        if run["status"] == "running":
            raise UadosError("Resolve the running experiment before interpreting it.")
        run.update(conclusion=conclusion, analysis_evidence=evidence_files(project.root, evidence), analyst=session["agent"])
        return {"experiment": experiment_id, "run": run["id"], "conclusion": conclusion}
    return project.mutate("experiment.conclude", conclusion, operation, session_id)
