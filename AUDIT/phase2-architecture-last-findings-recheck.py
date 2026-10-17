"""Independent recheck of the two findings outstanding at the interrupted review."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

repository = Path(sys.argv[1])
sys.path.insert(0, str(repository / "src"))
from uados.project import Project
from uados import governance as gov
from uados.storage import UadosError, safe_path

results = {}
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory) / "project"
    project = Project.initialize(root, "Malformed input recheck", "Reject malformed records cleanly")
    issued = project.start_session("Fixture author")
    project.acknowledge(issued["session"], issued["report_hash"])
    record = {"title": "Source", "identifier": "X", "url": "https://example.org/a", "claim": "Claim", "limitation": "Limitation", "access": "unavailable", "evidence": [7], "corpus": "Corpus"}
    (root / "record.json").write_text(json.dumps(record), encoding="utf-8")
    count_before = len(project.read()[1])
    command = [sys.executable, "-m", "uados", "--project", str(root), "research", "source", "--session", issued["session"], "--record", "record.json"]
    result = subprocess.run(command, env=dict(os.environ, PYTHONPATH=str(repository / "src")), capture_output=True, text=True)
    count_after = len(project.read()[1])
    results["malformed_array"] = {"passed": result.returncode == 2 and "Traceback" not in result.stderr and count_after == count_before, "exit_code": result.returncode, "stderr": result.stderr, "event_count_before": count_before, "event_count_after": count_after}
    try:
        safe_path(root, 7)
    except UadosError as error:
        results["invalid_path_type"] = {"passed": True, "error": str(error)}
    else:
        results["invalid_path_type"] = {"passed": False}

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory) / "project"
    project = Project.initialize(root, "Novelty policy recheck", "Keep policy versions visible", "research")
    (root / "evidence.txt").write_text("Mechanical evidence fixture; no novelty claim\n", encoding="utf-8")
    issued = project.start_session("Fixture idea author")
    author = issued["session"]
    project.acknowledge(author, issued["report_hash"])
    source = gov.add_source(project, author, "Unavailable source", "ID1", "https://example.org/source", "No retrieved claim", "Source unavailable; no novelty conclusion", "unavailable", ["evidence.txt"], "Corpus1")["source"]
    idea = gov.add_idea(project, author, "Inconclusive idea", {name: "Explicit bounded fixture for " + name for name in gov.IDEA_FIELDS}, [source], ["evidence.txt"])["idea"]
    issued = project.start_session("Fixture independent novelty reviewer")
    reviewer = issued["session"]
    project.acknowledge(reviewer, issued["report_hash"])
    gov.review_idea(project, reviewer, idea, "inconclusive", "Unavailable source is insufficient evidence, not absent prior work", ["evidence.txt"])
    clean_before = project.audit()
    policy = root / "RESEARCH_MANAGEMENT/innovation_policy.md"
    policy.write_text(policy.read_text(encoding="utf-8") + "\nNew assessment requirement for mechanical staleness probe.\n", encoding="utf-8")
    after = project.audit()
    stale = [warning for warning in after["warnings"] if "Stale novelty" in warning]
    results["novelty_policy_staleness"] = {"passed": not any("Stale novelty" in warning for warning in clean_before["warnings"]) and bool(stale), "warnings": stale, "audit_ok": after["ok"]}

print(json.dumps({"independent_mechanical_fixture": True, "command": ["python3", "AUDIT/phase2-architecture-last-findings-recheck.py", "REPOSITORY"], "results": results}, indent=2, sort_keys=True))
sys.exit(0 if all(item["passed"] for item in results.values()) else 1)
