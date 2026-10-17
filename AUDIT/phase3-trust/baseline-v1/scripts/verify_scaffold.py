"""Validate the packaged framework and an installed CLI without external services."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "src"))
from uados.context import REQUIRED_DIRECTORIES, REQUIRED_FILES
from uados.protocol import PROTOCOL_FILES


def main():
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(REPOSITORY / "src")
    with tempfile.TemporaryDirectory() as temporary:
        project = Path(temporary) / "project"
        def cli(*args):
            result = subprocess.run([sys.executable, "-m", "uados", *args], env=environment, text=True, capture_output=True)
            if result.returncode:
                raise RuntimeError(result.stderr or result.stdout)
            return json.loads(result.stdout)
        cli("init", str(project), "--name", "Verification", "--objective", "Check portable onboarding", "--mode", "hybrid")
        missing = [p for p in REQUIRED_DIRECTORIES + REQUIRED_FILES + PROTOCOL_FILES if not (project / p).exists()]
        if missing:
            raise RuntimeError("Missing required scaffold paths: " + ", ".join(missing))
        session = cli("--project", str(project), "session", "start", "--agent", "Verification-Agent")
        required_report = {"objective", "phase", "architecture", "completed_tasks", "current_problems", "known_risks", "available_resources", "recommended_next_actions", "execution_plan", "runtime"}
        if not required_report.issubset(session["report"]):
            raise RuntimeError("Understanding report omits required fields")
        cli("--project", str(project), "session", "acknowledge", session["session"], "--report-hash", session["report_hash"])
        cli("--project", str(project), "session", "close", session["session"], "--summary", "Verified onboarding", "--next", "Read context with replacement agent")
        audit = cli("--project", str(project), "audit")
        if not audit["ok"]:
            raise RuntimeError("Audit failed")
        print(json.dumps({"ok": True, "required_paths": len(REQUIRED_DIRECTORIES + REQUIRED_FILES), "events": audit["event_count"], "packaged_markdown_files": len(list((REPOSITORY / "src/uados/assets").rglob("*.md")))}, indent=2))


if __name__ == "__main__":
    main()
