"""Verify the built wheel and a real disposable Git clone, without remote writes."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))
from uados.project import Project
from uados.storage import project_lock


def run(command, cwd, environment=None):
    result = subprocess.run(command, cwd=str(cwd), env=environment, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("Command failed (%d): %s\n%s" % (result.returncode, command, result.stderr))
    return result.stdout


def main():
    arguments = argparse.ArgumentParser(description=__doc__)
    arguments.add_argument("--wheel", type=Path, default=REPOSITORY / "dist/uados-1.1.0-py3-none-any.whl")
    arguments.add_argument("--python", type=Path, required=True, help="Interpreter in an environment with the wheel installed")
    arguments.add_argument("--output", type=Path, default=REPOSITORY / "AUDIT/phase2-distribution.json")
    args = arguments.parse_args()
    wheel = args.wheel.absolute()
    interpreter = args.python.absolute()  # Keep the venv symlink; resolving it selects the base interpreter.
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    with zipfile.ZipFile(wheel) as archive:
        assets = [name for name in archive.namelist() if name.startswith("uados/assets/") and Path(name).suffix in {".md", ".mdc"}]
        expected_assets = {p.relative_to(REPOSITORY / "src").as_posix() for p in (REPOSITORY / "src/uados/assets").rglob("*") if p.is_file() and p.suffix in {".md", ".mdc"}}
        assert set(assets) == expected_assets, (assets, expected_assets)
        for source in (REPOSITORY / "src/uados").rglob("*"):
            if source.is_file() and source.suffix in {".py", ".md", ".mdc"} and "__pycache__" not in source.parts:
                archive_path = source.relative_to(REPOSITORY / "src").as_posix()
                assert archive.read(archive_path) == source.read_bytes(), "Wheel differs from current source: " + archive_path
    with tempfile.TemporaryDirectory(prefix="uados-distribution-") as temporary:
        temporary = Path(temporary)
        project = temporary / "installed-project"
        def cli(*values):
            return json.loads(run([str(interpreter), "-m", "uados", *values], temporary, environment))
        location = run([str(interpreter), "-c", "import uados; print(uados.__file__)"], temporary, environment).strip()
        assert "site-packages" in location, location
        cli("init", str(project), "--name", "Installed distribution", "--objective", "Check isolated package and assets", "--mode", "hybrid")
        report = cli("--project", str(project), "session", "start", "--agent", "Distribution-Verification")
        cli("--project", str(project), "session", "acknowledge", report["session"], "--report-hash", report["report_hash"])
        cli("--project", str(project), "session", "close", report["session"], "--summary", "Installed distribution verified", "--next", "Continue from durable project files")
        installed_audit = cli("--project", str(project), "audit")
        assert installed_audit["ok"], installed_audit

        snapshot = temporary / "snapshot"
        snapshot.mkdir()
        # Copy precisely the files the user's Git ignore policy permits, while memory is stable.
        with project_lock(REPOSITORY):
            files = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=str(REPOSITORY), capture_output=True, check=True).stdout.decode("utf-8").split("\0")
            files = [name for name in files if name]
            assert ".uados/events.jsonl" in files
            assert not any(name.endswith("ledger.sqlite3") for name in files)
            for mode in ("research", "hybrid"):
                assert "EXAMPLES/generated/%s/.uados/runs/E000001/R000001/stdout.txt" % mode in files
            for relative in files:
                destination = snapshot / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(REPOSITORY / relative, destination)
        run(["git", "init", "--initial-branch=main"], snapshot)
        run(["git", "add", "--all"], snapshot)
        run(["git", "-c", "user.name=UADOS validation", "-c", "user.email=uados-validation@localhost", "commit", "-m", "Disposable validation snapshot"], snapshot)
        clone = temporary / "clone"
        run(["git", "clone", "--quiet", str(snapshot), str(clone)], temporary)
        assert not (clone / ".uados/ledger.sqlite3").exists()
        rebuilt = Project.rebuild_ledger(clone)
        clone_audits = {"repository": Project(clone).audit()}
        for mode in ("software", "research", "hybrid"):
            example = clone / "EXAMPLES/generated" / mode
            Project.rebuild_ledger(example)
            clone_audits[mode] = Project(example).audit()
        for relative in ("software", "research", "handover/day1", "handover/day30"):
            example = clone / "EXAMPLES/phase2-final" / relative
            if example.exists():
                Project.rebuild_ledger(example)
                clone_audits["phase2/" + relative] = Project(example).audit()
        assert all(item["ok"] for item in clone_audits.values()), clone_audits
        summary = {"ok": True, "command": ["python3", "scripts/verify_distribution.py", "--python", str(args.python)],
                   "wheel": str(wheel), "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
                   "packaged_assets": len(assets), "wheel_matches_current_package_source": True,
                   "installed_import": location, "installed_audit": installed_audit,
                   "real_local_git_clone": True, "git_file_count": len(files), "rebuild": rebuilt,
                   "clone_audits": clone_audits,
                   "note": "Temporary commit/clone only; no remote writes. Historical scope-change warnings are retained for inspection."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
