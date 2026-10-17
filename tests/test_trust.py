"""Real SSHSIG and independent pin/policy/ledger/publication failure boundaries."""

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from uados.project import Project, write_projections
from uados.storage import UadosError, canonical, digest
from uados import trust


@unittest.skipUnless(shutil.which("ssh-keygen"), "OpenSSH executable unavailable; real SSHSIG checks not executed")
class Trust(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="uados-trust-test-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name).resolve()
        self.root = self.directory / "project"
        self.p = Project.initialize(self.root, "Trust", "Preserve a verifiable external anchor")
        self.key = self.directory / "key"
        self.key2 = self.directory / "key2"
        for path in (self.key, self.key2):
            subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(path)], check=True, capture_output=True)
        self.allowed = self.directory / "allowed"
        self.allowed.write_text('alice namespaces="%s" %s\n' % (trust.NAMESPACE, self.key.with_suffix(".pub").read_text().strip()))
        self.bundle = self.directory / "bundle"

    def create(self):
        return trust.create_checkpoint(self.p, self.bundle, "alice", self.key)

    def verify(self, result, **extra):
        return trust.verify_checkpoint(self.p, self.bundle, "alice", result["checkpoint_sha256"], self.allowed, **extra)

    def resign(self, value, namespace=trust.NAMESPACE, raw=None):
        message = self.bundle / "checkpoint.json"
        message.write_bytes(raw if raw is not None else (canonical(value) + "\n").encode())
        signature = self.bundle / "checkpoint.json.sig"
        signature.unlink()
        subprocess.run(["ssh-keygen", "-Y", "sign", "-f", str(self.key), "-n", namespace, str(message)], check=True, capture_output=True)
        pin = hashlib.sha256(message.read_bytes()).hexdigest()
        marker = {"checkpoint_sha256": pin, "signature_sha256": hashlib.sha256(signature.read_bytes()).hexdigest()}
        (self.bundle / "COMPLETE").write_text(canonical(marker) + "\n")
        return {"checkpoint_sha256": pin}

    def test_real_current_checkpoint_and_no_ledger_mutation(self):
        before = {path: (self.root / path).read_bytes() for path in (".uados/events.jsonl", ".uados/state.json", "PROJECT_STATE.md")}
        result = self.create()
        checked = self.verify(result, require_current=True)
        self.assertTrue(checked["ok"] and checked["signature_verified"] and checked["covers_current_head"])
        self.assertEqual(checked["current_sequence"], 1)
        self.assertEqual(before, {path: (self.root / path).read_bytes() for path in before})
        self.assertFalse(any(path.name in {"key", "key.pub", "allowed"} for path in self.root.rglob("*")))

    def test_historical_prefix_explicit_and_current_requirement(self):
        result = self.create()
        self.p.start_session("Later")
        checked = self.verify(result)
        self.assertTrue(checked["ok"])
        self.assertFalse(checked["covers_current_head"])
        self.assertEqual(checked["current_sequence"], 2)
        with self.assertRaisesRegex(UadosError, "historical prefix"):
            self.verify(result, require_current=True)

    def test_external_pin_rejects_substituted_legitimate_checkpoint(self):
        old = self.create()
        self.p.start_session("Later")
        second = self.directory / "second"
        new = trust.create_checkpoint(self.p, second, "alice", self.key)
        with self.assertRaisesRegex(UadosError, "trusted SHA256 pin"):
            trust.verify_checkpoint(self.p, self.bundle, "alice", new["checkpoint_sha256"], self.allowed)
        self.assertNotEqual(old["checkpoint_sha256"], new["checkpoint_sha256"])

    def test_wrong_identity_key_namespace_and_revocation_rejected(self):
        result = self.create()
        with self.assertRaisesRegex(UadosError, "authorized verification failed"):
            trust.verify_checkpoint(self.p, self.bundle, "mallory", result["checkpoint_sha256"], self.allowed)
        original = self.allowed.read_text()
        self.allowed.write_text("alice " + self.key2.with_suffix(".pub").read_text())
        with self.assertRaises(UadosError):
            self.verify(result)
        self.allowed.write_text(original)
        revoked = self.directory / "revoked"
        revoked.write_text(self.key.with_suffix(".pub").read_text())
        with self.assertRaisesRegex(UadosError, "authorized verification failed"):
            self.verify(result, revocations=revoked)
        value = json.loads((self.bundle / "checkpoint.json").read_text())
        result = self.resign(value, namespace="other@uados.local")
        with self.assertRaisesRegex(UadosError, "authorized verification failed"):
            self.verify(result)

    def test_operator_key_rotation_and_policy_digest(self):
        old = self.create()
        self.allowed.write_text("alice " + self.key2.with_suffix(".pub").read_text())
        second = self.directory / "rotated"
        new = trust.create_checkpoint(self.p, second, "alice", self.key2)
        checked = trust.verify_checkpoint(self.p, second, "alice", new["checkpoint_sha256"], self.allowed)
        self.assertTrue(checked["signature_verified"])
        self.assertEqual(checked["allowed_signers_sha256"], hashlib.sha256(self.allowed.read_bytes()).hexdigest())
        with self.assertRaises(UadosError):
            self.verify(old)

    def test_signed_inconsistent_state_and_project_rejected(self):
        self.create()
        value = json.loads((self.bundle / "checkpoint.json").read_text())
        value["state_sha256"] = "0" * 64
        with self.assertRaisesRegex(UadosError, "prefix/state"):
            self.verify(self.resign(value))
        value["project_id"] = "0" * 64
        with self.assertRaisesRegex(UadosError, "project or sequence"):
            self.verify(self.resign(value))

    def test_rehashed_forged_ledger_rejected_by_anchor(self):
        self.p.start_session("Original")
        result = self.create()
        state, events, _ = self.p.read()
        state["objective"] = "Forged after signing"
        events[-1]["state"] = state
        unsigned = {k: v for k, v in events[-1].items() if k != "hash"}
        events[-1]["hash"] = digest(unsigned)
        with sqlite3.connect(str(self.root / ".uados/ledger.sqlite3")) as connection:
            connection.execute("UPDATE state SET value=? WHERE id=1", (canonical(state),))
            connection.execute("UPDATE events SET value=? WHERE sequence=?", (canonical(events[-1]), len(events)))
        write_projections(self.root, state, events)
        self.assertTrue(self.p.audit()["ok"])
        with self.assertRaisesRegex(UadosError, "prefix/state"):
            self.verify(result)

    def test_latest_external_pin_rejects_truncated_ledger(self):
        self.p.start_session("Original")
        result = self.create()
        _, events, _ = self.p.read()
        first = events[0]
        with sqlite3.connect(str(self.root / ".uados/ledger.sqlite3")) as connection:
            connection.execute("DELETE FROM events WHERE sequence>1")
            connection.execute("UPDATE state SET value=? WHERE id=1", (canonical(first["state"]),))
        write_projections(self.root, first["state"], [first])
        self.assertTrue(self.p.audit()["ok"])
        with self.assertRaisesRegex(UadosError, "project or sequence"):
            self.verify(result, require_current=True)

    def test_live_audit_failure_does_not_invalidate_historical_signature_claim(self):
        result = self.create()
        (self.root / "PROJECT_STATE.md").write_text("Edited generated view")
        checked = self.verify(result)
        self.assertFalse(checked["ok"])
        self.assertTrue(checked["signature_verified"])
        self.assertTrue(checked["signed_audit_assertion"]["current_ok"])
        self.assertFalse(checked["current_audit"]["ok"])
        with self.assertRaisesRegex(UadosError, "Current audit failed"):
            trust.create_checkpoint(self.p, self.directory / "bad", "alice", self.key)

    def test_duplicate_noncanonical_unknown_bool_and_nonfinite_payloads(self):
        self.create()
        value = json.loads((self.bundle / "checkpoint.json").read_text())
        variants = [dict(value, sequence=True), dict(value, version=True), dict(value, unknown="field")]
        for bad in variants:
            with self.subTest(bad=bad):
                with self.assertRaises(UadosError):
                    self.verify(self.resign(bad))
        for raw in (b'{"format":"uados-checkpoint","format":"other"}\n', b'{"number":NaN}\n', json.dumps(value, indent=2).encode()):
            with self.assertRaises(UadosError):
                self.verify(self.resign(value, raw=raw))

    def test_marker_missing_corrupt_signature_and_size_limits(self):
        result = self.create()
        marker = self.bundle / "COMPLETE"
        original = marker.read_bytes()
        marker.unlink()
        with self.assertRaises(UadosError):
            self.verify(result)
        marker.write_bytes(original)
        (self.bundle / "checkpoint.json.sig").write_text("invalid")
        marker.write_text(canonical({"checkpoint_sha256":result["checkpoint_sha256"], "signature_sha256":hashlib.sha256(b"invalid").hexdigest()})+"\n")
        with self.assertRaisesRegex(UadosError, "authorized verification failed"):
            self.verify(result)
        (self.bundle / "checkpoint.json").write_bytes(b"x" * (trust.LIMIT + 1))
        with self.assertRaisesRegex(UadosError, "size limit"):
            self.verify(result)

    def test_output_immutable_and_internal_paths_rejected(self):
        self.create()
        before = {p.name: p.read_bytes() for p in self.bundle.iterdir()}
        with self.assertRaises(UadosError):
            self.create()
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.bundle.iterdir()})
        for key, output in ((self.root / "internal-key", self.directory / "new"), (self.key, self.root / "anchor")):
            with self.assertRaises(UadosError):
                trust.create_checkpoint(self.p, output, "alice", key)
        with self.assertRaises(UadosError):
            trust.verify_checkpoint(self.p, self.bundle, "*", "x", self.allowed)

    @unittest.skipUnless(os.name == "posix", "Symlink permissions vary on Windows")
    def test_symlink_and_path_traversal_rejected(self):
        result = self.create()
        alias = self.directory / "alias"
        alias.symlink_to(self.allowed)
        with self.assertRaisesRegex(UadosError, "symlinks"):
            trust.verify_checkpoint(self.p, self.bundle, "alice", result["checkpoint_sha256"], alias)
        with self.assertRaisesRegex(UadosError, "'..'"):
            trust.create_checkpoint(self.p, self.directory / "x/../new", "alice", self.key)

    def test_missing_tool_timeout_failure_cleanup_and_audit_race(self):
        for patch, reason in ((mock.patch("uados.trust.shutil.which", return_value=None), "require OpenSSH"),
                              (mock.patch("uados.trust.subprocess.run", side_effect=subprocess.TimeoutExpired("ssh-keygen", 15)), "timed out")):
            with patch, self.assertRaisesRegex(UadosError, reason):
                self.create()
            self.assertFalse(self.bundle.exists())
            self.assertFalse(list(self.directory.glob(".uados-checkpoint-*")))
        real_audit = self.p.audit
        def raced():
            audit = real_audit()
            self.p.start_session("Race")
            return audit
        with mock.patch.object(self.p, "audit", side_effect=raced), self.assertRaisesRegex(UadosError, "between audit"):
            self.create()
        self.assertFalse(self.bundle.exists())

    def test_concurrent_cli_publication_has_one_winner_and_valid_bundle(self):
        environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
        command = [sys.executable, "-m", "uados", "--project", str(self.root), "trust", "checkpoint",
                   "--output", str(self.bundle), "--principal", "alice", "--key", str(self.key)]
        processes = [subprocess.Popen(command, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
        results = [(p.communicate(timeout=30), p.returncode) for p in processes]
        self.assertEqual(sorted(code for _, code in results), [0, 2])
        winner = next(json.loads(stdout) for (stdout, _), code in results if code == 0)
        self.assertTrue(self.verify(winner, require_current=True)["ok"])
        self.assertEqual(self.p.audit()["event_count"], 1)

    def test_publication_disk_failure_leaves_rejected_incomplete_bundle(self):
        original_link = os.link
        count = 0
        def fail_second(source, destination):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError("Injected publication disk failure")
            return original_link(source, destination)
        with mock.patch("uados.trust.os.link", side_effect=fail_second), self.assertRaises(OSError):
            self.create()
        self.assertEqual({p.name for p in self.bundle.iterdir()}, {"checkpoint.json"})
        self.assertFalse(list(self.directory.glob(".uados-checkpoint-*")))
        pin = hashlib.sha256((self.bundle / "checkpoint.json").read_bytes()).hexdigest()
        with self.assertRaises(UadosError):
            self.verify({"checkpoint_sha256": pin})
        with self.assertRaises(UadosError):
            self.create()
        self.assertEqual(self.p.audit()["event_count"], 1)


if __name__ == "__main__":
    unittest.main()
