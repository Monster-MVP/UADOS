import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from uados.dispatch import run_dispatch, verify_receipt
from uados.project import Project
from uados.storage import UadosError


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.parent = Path(self.tmp.name).resolve()
        self.root = self.parent / "project"
        self.project = Project.initialize(self.root, "dispatch", "receipt mechanics")
        (self.root / "request.json").write_text(json.dumps({"format": "uados-dispatch-request", "version": 1, "provider": "fake", "operation": "summarize", "input": {"value": "x"}}, sort_keys=True, separators=(",", ":")) + "\n")

    def test_deterministic_fake_receipt_and_verification_without_ledger_mutation(self):
        before = len(self.project.read()[1])
        first = self.parent / "receipt-1.json"
        second = self.parent / "receipt-2.json"
        a = run_dispatch(self.project, "request.json", str(first))
        b = run_dispatch(self.project, "request.json", str(second))
        self.assertEqual(a["response_sha256"], b["response_sha256"])
        self.assertEqual(verify_receipt(self.project, "request.json", str(first))["verified"], True)
        self.assertEqual(len(self.project.read()[1]), before)

    def test_request_shape_unknown_provider_and_tamper_fail_without_receipt(self):
        output = self.parent / "receipt.json"
        bad = {"format": "uados-dispatch-request", "version": True, "provider": "fake", "operation": "x", "input": {}}
        (self.root / "bad.json").write_text(json.dumps(bad, separators=(",", ":")) + "\n")
        with self.assertRaises(UadosError):
            run_dispatch(self.project, "bad.json", str(output))
        self.assertFalse(output.exists())
        unknown = {"format": "uados-dispatch-request", "version": 1, "provider": "real", "operation": "x", "input": {}}
        (self.root / "unknown.json").write_text(json.dumps(unknown, sort_keys=True, separators=(",", ":")) + "\n")
        with self.assertRaises(UadosError):
            run_dispatch(self.project, "unknown.json", str(output))
        good = self.parent / "good.json"
        run_dispatch(self.project, "request.json", str(good))
        good.write_text(good.read_text().replace("succeeded", "failed"))
        with self.assertRaises(UadosError):
            verify_receipt(self.project, "request.json", str(good))

    def test_request_drift_and_nonfinite_duplicate_payloads_fail(self):
        duplicate = self.root / "duplicate.json"
        duplicate.write_bytes(b'{"format":"uados-dispatch-request","format":"x","version":1,"provider":"fake","operation":"x","input":{}}\n')
        with self.assertRaises(UadosError):
            run_dispatch(self.project, "duplicate.json", str(self.parent / "duplicate-receipt.json"))
        drift_receipt = self.parent / "drift-receipt.json"
        run_dispatch(self.project, "request.json", str(drift_receipt))
        request = json.loads((self.root / "request.json").read_text())
        request["input"]["value"] = "changed"
        (self.root / "request.json").write_text(json.dumps(request, sort_keys=True, separators=(",", ":")) + "\n")
        with self.assertRaises(UadosError):
            verify_receipt(self.project, "request.json", str(drift_receipt))

    def test_output_internal_existing_symlink_and_traversal_rejected(self):
        with self.assertRaises(UadosError):
            run_dispatch(self.project, "request.json", str(self.root / "inside.json"))
        existing = self.parent / "existing.json"
        existing.write_text("x")
        with self.assertRaises(UadosError):
            run_dispatch(self.project, "request.json", str(existing))
        with self.assertRaises(UadosError):
            run_dispatch(self.project, "request.json", str(self.parent / ".." / "bad.json"))

    def test_cli_fake_run_and_verify(self):
        output = self.parent / "cli-receipt.json"
        cmd = [sys.executable, "-m", "uados", "--project", str(self.root), "dispatch", "run", "--request", "request.json", "--output", str(output)]
        env = dict(__import__("os").environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        verify = subprocess.run([sys.executable, "-m", "uados", "--project", str(self.root), "dispatch", "verify", "--request", "request.json", "--receipt", str(output)], env=env, capture_output=True, text=True)
        self.assertEqual(verify.returncode, 0, verify.stderr)

    def test_existing_receipt_traversal_and_parent_alias_are_rejected(self):
        output = self.parent / "receipt.json"
        run_dispatch(self.project, "request.json", str(output))
        inside = self.root / "copy.json"
        inside.write_bytes(output.read_bytes())
        alias = self.parent / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(UadosError):
            verify_receipt(self.project, "request.json", str(alias / "copy.json"))
        (self.parent / "directory").mkdir()
        with self.assertRaises(UadosError):
            verify_receipt(self.project, "request.json", str(self.parent / "directory" / ".." / "receipt.json"))
        external_alias = self.parent / "external-alias"
        external_alias.symlink_to(self.parent / "directory", target_is_directory=True)
        with self.assertRaises(UadosError):
            run_dispatch(self.project, "request.json", str(external_alias / "new.json"))

    def test_invalid_naive_or_reversed_receipt_timestamps_are_rejected(self):
        output = self.parent / "receipt.json"
        run_dispatch(self.project, "request.json", str(output))
        original = json.loads(output.read_text())
        for started, ended in (("bad", "bad"), ("2026-10-14", "2026-10-14"),
                               ("2026-10-14T03:00:00+00:00", "2026-10-14T02:00:00+00:00")):
            altered = dict(original, started_at=started, ended_at=ended)
            output.write_text(json.dumps(altered, sort_keys=True, separators=(",", ":")) + "\n")
            with self.assertRaises(UadosError):
                verify_receipt(self.project, "request.json", str(output))

    def test_unpaired_unicode_surrogate_is_a_clean_cli_error(self):
        value = {"format": "uados-dispatch-request", "version": 1, "provider": "fake", "operation": "x", "input": "\ud800"}
        (self.root / "surrogate.json").write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
        output = self.parent / "surrogate-receipt.json"
        with self.assertRaises(UadosError):
            run_dispatch(self.project, "surrogate.json", str(output))
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
        result = subprocess.run([sys.executable, "-m", "uados", "--project", str(self.root),
                                 "dispatch", "run", "--request", "surrogate.json", "--output", str(output)],
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("error", json.loads(result.stderr))
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
