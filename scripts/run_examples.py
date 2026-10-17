"""Executable software/research/hybrid adoption scenarios in fresh directories."""

import argparse
import json
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))
from uados.project import Project
from uados.research import add_experiment, conclude_experiment, run_experiment


def acknowledge(project, agent):
    report = project.start_session(agent)
    project.acknowledge(report["session"], report["report_hash"])
    return report["session"]


def refresh(project, session):
    report = project.refresh_session(session)
    project.acknowledge(session, report["report_hash"])


def write(root, path, text):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return path


def software(root, mode="software"):
    project = Project.initialize(root, "Portable software example", "Implement a reviewed function and hand off to another agent", mode, protocol_version=1)
    implementer = acknowledge(project, "Example-Builder")
    write(root, "app.py", "def add(a, b):\n    raise NotImplementedError\n")
    task = project.add_task(implementer, "Add integers", "Return integer sums; validate zero, negatives and mixed signs", "major", ["app.py"])["task"]
    review_evidence = write(root, "evidence/design-review.md", "Challenge: would signed values or zero fail? Use Python integer addition; no conversion or hidden state. Test negative and zero cases.")
    reviewer = acknowledge(project, "Example-Reviewer")
    project.review_task(reviewer, task, "plan", "approve", "Challenged numeric edge cases and state mutation; simple pure function addresses them", [review_evidence])
    refresh(project, implementer)
    project.claim_task(implementer, task)
    write(root, "app.py", "def add(a, b):\n    return a + b\n")
    namespace = {}
    exec((root / "app.py").read_text(), namespace)
    for a, b, expected in ((0, 0, 0), (-2, -3, -5), (-2, 3, 1)):
        assert namespace["add"](a, b) == expected
    evidence = write(root, "evidence/tests.json", json.dumps({"cases": 3, "passed": 3, "method": "Assertions against explicit expected values"}))
    project.record_task(implementer, task, "Implemented integer addition; verified zero and negative cases", [evidence])
    refresh(project, reviewer)
    project.review_task(reviewer, task, "result", "approve", "Inspected implementation and independently checked edge case evidence; no stateful behavior", [evidence])
    refresh(project, implementer)
    project.complete_task(implementer, task)
    project.add_note(implementer, "Rejected approach", "Rejected coercing arguments to int: it silently truncates fractions and changes caller semantics", "failure")
    project.close_session(implementer, "Reviewed function complete", ["Decide whether to expand the numeric contract"], [], ["Implicit integer coercion rejected"])
    project.close_session(reviewer, "Independent review complete", ["Review any future contract expansion"])
    replacement = project.start_session("Example-Successor")
    assert replacement["report"]["completed_tasks"] and replacement["report"]["failed_approaches"]
    project.acknowledge(replacement["session"], replacement["report_hash"])
    project.close_session(replacement["session"], "Recovered completed work and rejected approach", ["Await the next requested feature"])
    return project


def research(root, existing=None):
    project = existing or Project.initialize(root, "Reproducible research example", "Test a fixture mean while preserving data provenance and uncertainty", "research", protocol_version=1)
    session = acknowledge(project, "Example-Researcher")
    script = write(root, "study.py", "import csv, json, random\nfrom statistics import mean\nrandom.seed(7)\nwith open('dataset.csv', newline='') as stream:\n    values = [float(row['value']) for row in csv.DictReader(stream)]\nprint(json.dumps({'mean': mean(values), 'n': len(values), 'seed': 7}))\n")
    config = write(root, "study-config.json", '{"seed":7,"metric":"arithmetic mean"}\n')
    data = write(root, "dataset.csv", "value\n1\n2\n3\n")
    experiment = add_experiment(project, session, "Fixture mean", "For values 1, 2, 3, arithmetic mean equals 2; no broader generalization", [sys.executable, "study.py"], config, [data], 7, [script])["experiment"]
    result = run_experiment(project, session, experiment, 10)
    assert result["status"] == "succeeded"
    observed = json.loads((root / result["stdout"]).read_text())
    assert observed["mean"] == 2 and observed["n"] == 3
    refresh(project, session)
    analysis = write(root, "evidence/analysis.md", "Observed mean 2.0 from 3 fixed fixture values. This validates arithmetic only; no sampling uncertainty or population claim is supported.")
    conclude_experiment(project, session, experiment, "Fixture hypothesis supported. Three deterministic inputs cannot justify a population inference.", [analysis])
    project.add_note(session, "Research limitation", "Seed is explicitly applied in the script; real experiments need design, replicates, missing-data treatment and uncertainty estimates", "research")
    project.close_session(session, "Ran and interpreted fixture experiment", ["Design representative sampling before any scientific claim"])
    return project


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--output", type=Path, required=True, help="New directory; contains three initialized example projects")
    destination = args.parse_args().output.resolve()
    if destination.exists():
        raise SystemExit("Example output must be a new directory; nothing is overwritten.")
    destination.mkdir(parents=True)
    outcomes = {}
    for mode in ("software", "research", "hybrid"):
        root = destination / mode
        if mode == "software":
            project = software(root)
        elif mode == "research":
            project = research(root)
        else:
            project = software(root, "hybrid")
            project = research(root, project)
        result = project.audit()
        assert result["ok"], result
        outcomes[mode] = {"project": str(root), "audit": result}
    print(json.dumps(outcomes, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
