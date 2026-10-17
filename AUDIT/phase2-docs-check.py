"""Replay the bounded Phase 2 documentation checks; print JSON without modifying records."""

import contextlib
import hashlib
import io
import json
import platform
import re
import shlex
import subprocess
import sys
import tempfile
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from uados.cli import parser, read_record
from uados.governance import IDEA_FIELDS


def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check():
    common = [Path(name) for name in (
        "MASTER_AGENT_WORKFLOW.md", "AGENTS.md", "CLAUDE.md",
        "ENGINEERING_RULES/README.md", "ENGINEERING_RULES/quality.md",
        "RESEARCH_MANAGEMENT/innovation_policy.md",
    )]
    for folder in (".agent", ".cursor", "MULTI_AGENT_SYSTEM", "CHANGE_REQUESTS"):
        common.extend(p.relative_to(ROOT) for p in (ROOT / folder).rglob("*")
                      if p.is_file() and p.suffix in {".md", ".mdc"}
                      and p.name != "role_plans.md"
                      and not (p.parent.name == "CHANGE_REQUESTS" and p.stem[2:].isdigit()))
    for relative in common:
        assert (ROOT / relative).read_bytes() == (ROOT / "src/uados/assets" / relative).read_bytes(), str(relative)

    root_docs = sorted(set(common + [Path(name) for name in (
        "README.md", "docs/architecture.md", "docs/requirements.md",
        "docs/adr/0002-phase2-governance.md", "PROJECT_MEMORY/architecture.md",
    )]))
    links = []
    for relative in root_docs:
        for target in re.findall(r"\]\(([^)]+)\)", (ROOT / relative).read_text()):
            path = target.split("#")[0]
            if path and "://" not in path:
                assert (ROOT / relative.parent / path).is_file(), [str(relative), target]
                links.append([str(relative), target])

    commands = []
    for name in ("README.md", "MASTER_AGENT_WORKFLOW.md", "MULTI_AGENT_SYSTEM/debate_protocol.md"):
        for body in re.findall(r"```sh\n(.*?)```", (ROOT / name).read_text(), re.S):
            for line in body.replace("\\\n", " ").splitlines():
                argv = shlex.split(line)
                args = argv[3:] if argv[:3] == ["python", "-m", "uados"] else argv[2:] if argv[:2] == ["python3", "scripts/uados.py"] else None
                if args is None:
                    continue
                try:
                    with contextlib.redirect_stdout(io.StringIO()):
                        parser().parse_args(args)
                except SystemExit as exc:
                    assert exc.code == 0 and "--help" in args, args
                commands.append({"file": name, "argv": args})

    schemas = {
        "CHANGE_REQUESTS/CR_TEMPLATE.md": [
            ("problem", "background", "alternatives", "decision", "impact", "risk", "validation", "evidence"),
        ],
        "RESEARCH_MANAGEMENT/innovation_policy.md": [
            ("title", "identifier", "url", "claim", "limitation", "access", "evidence", "corpus"),
            ("title", "fields", "sources", "evidence"),
            ("idea", "prediction", "baseline", "metric", "rejection", "uncertainty", "evidence"),
        ],
    }
    forms = []
    with tempfile.TemporaryDirectory(prefix="uados-doc-schema-") as directory:
        project = types.SimpleNamespace(root=Path(directory))
        for name, field_lists in schemas.items():
            blocks = re.findall(r"```json\n(.*?)```", (ROOT / name).read_text(), re.S)
            assert len(blocks) == len(field_lists), name
            for block, fields in zip(blocks, field_lists):
                value = json.loads(block)
                (project.root / "record.json").write_text(block)
                read_record(project, "record.json", fields)
                if "fields" in value:
                    assert all(isinstance(value["fields"].get(field), str) and value["fields"][field] for field in IDEA_FIELDS)
                forms.append({"file": name, "fields": list(fields)})

    for name in ("AGENTS.md", "CLAUDE.md", ".cursor/rules/uados.mdc"):
        assert "MASTER_AGENT_WORKFLOW.md" in (ROOT / name).read_text(), name
    assert "@MASTER_AGENT_WORKFLOW.md" in (ROOT / "CLAUDE.md").read_text()
    wrapper = (ROOT / ".cursor/rules/uados.mdc").read_text()
    assert wrapper.startswith("---\n") and "alwaysApply: true" in wrapper and "explicitly open" in wrapper

    baseline = json.loads((ROOT / "AUDIT/phase2-baseline.json").read_text())
    preserved = {name: value for name, value in baseline["files"].items()
                 if name.startswith(("AUDIT/", "EXAMPLES/generated/", "PROJECT_MEMORY/session_reports/"))
                 or name in {"docs/adr/0001-local-ledger.md", "PROJECT_MEMORY/notes/initial-understanding.md"}}
    assert all((ROOT / name).is_file() and hash_file(ROOT / name) == value for name, value in preserved.items())
    events = [json.loads(line) for line in (ROOT / ".uados/events.jsonl").read_text().splitlines()]
    assert [event["hash"] for event in events[:len(baseline["event_hashes"])]] == baseline["event_hashes"]

    scaffold_command = [sys.executable, "scripts/verify_scaffold.py"]
    scaffold = subprocess.run(scaffold_command, cwd=ROOT, text=True, capture_output=True)
    assert scaffold.returncode == 0, scaffold.stdout + scaffold.stderr

    assets = [p for p in (ROOT / "src/uados/assets").rglob("*") if p.is_file()]
    assert len(assets) == 48 and any(p.suffix == ".mdc" for p in assets)

    runner = ROOT / "scripts/run_phase2_scenarios.py"
    if runner.is_file():
        command = [sys.executable, str(runner), "--help"]
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        assert result.returncode == 0 and "--output" in result.stdout, result.stdout + result.stderr
        runner_check = {"status": "passed", "command": command, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    else:
        runner_check = {"status": "pending_parent_integration", "owner_task": "T000004", "reason": "Scenario runner is not yet present; no passing invocation claim is made."}

    return {
        "ok_documentation_checks": True,
        "environment": {"python": sys.version, "platform": platform.platform()},
        "root_package_pairs": len(common),
        "root_scoped_documents": len(root_docs),
        "local_links_checked": links,
        "documented_cli_forms": commands,
        "documented_json_shapes": forms,
        "native_loader_metadata": "Thin master references; CLAUDE import and alwaysApply .mdc wrapper checked as files, not commercial-client execution.",
        "packaged_maintained_asset_count": len(assets),
        "preserved_baseline_events": len(baseline["event_hashes"]),
        "preserved_historical_files": len(preserved),
        "scaffold": {"command": scaffold_command, "exit_code": scaffold.returncode, "stdout": scaffold.stdout, "stderr": scaffold.stderr},
        "scenario_runner_help": runner_check,
        "file_hashes": {str(p): hash_file(ROOT / p) for p in root_docs},
        "limits": [
            "Parser/schema checks validate documented input forms, not runtime behavior; T000004 scenarios and regression tests establish behavior.",
            "Isolated wheel/Git verification belongs to T000004 integration validation; this result does not claim those unexecuted checks passed.",
            "Official loader documentation checked 2026-10-12; native commercial clients were not launched by these checks.",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(check(), indent=2, ensure_ascii=False, sort_keys=True))
