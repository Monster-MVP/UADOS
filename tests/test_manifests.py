import hashlib
import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from uados.project import Project, check_evidence
from uados.storage import UadosError, evidence_files
from uados import governance


class ManifestEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "project"
        self.project = Project.initialize(self.root, "manifest", "bounded closure")

    def write(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def manifest(self, name, entries):
        value = {"format": "uados-evidence-manifest", "version": 1, "files": entries}
        return self.write(name, (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode())

    def entry(self, name, kind="file"):
        data = (self.root / name).read_bytes()
        return {"path": name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "kind": kind}

    def test_nested_shared_binary_graph_is_flat_and_exact(self):
        self.write("shared.bin", b"\x00\xff\x01")
        self.manifest("child.uados-manifest.json", [self.entry("shared.bin")])
        root = self.manifest("root.uados-manifest.json", [self.entry("child.uados-manifest.json", "manifest"), self.entry("shared.bin")])
        records = evidence_files(self.root, [root.relative_to(self.root).as_posix()])
        self.assertEqual(len(records), 1)
        self.assertEqual([x["path"] for x in records[0]["dependencies"]], ["child.uados-manifest.json", "shared.bin"])
        self.assertEqual(check_evidence(self.root, records), [])

    def test_leaf_drift_invalidates_root_and_old_snapshot_is_not_live_substitute(self):
        self.write("leaf.bin", b"before")
        root = self.manifest("root.uados-manifest.json", [self.entry("leaf.bin")])
        record = evidence_files(self.root, [root.relative_to(self.root).as_posix()])[0]
        self.write("leaf.bin", b"after")
        self.assertTrue(any("Evidence changed" in value for value in check_evidence(self.root, [record])))

    def test_invalid_manifest_does_not_publish_a_snapshot(self):
        bad = self.write("bad.uados-manifest.json", b'{"format":"uados-evidence-manifest","version":1,"files":[}')
        before = sorted((self.root / ".uados/evidence/sha256").glob("*"))
        with self.assertRaises(UadosError):
            evidence_files(self.root, [bad.relative_to(self.root).as_posix()])
        self.assertEqual(before, sorted((self.root / ".uados/evidence/sha256").glob("*")))

    def test_kind_path_and_legacy_json_rules(self):
        self.write("ordinary.json", b'{"not":"a manifest"}\n')
        self.assertEqual(len(evidence_files(self.root, ["ordinary.json"])), 1)
        self.write("leaf.bin", b"x")
        bad = self.manifest("bad.uados-manifest.json", [{"path": "leaf.bin", "sha256": "0" * 64, "bytes": 1, "kind": "manifest"}])
        with self.assertRaises(UadosError):
            evidence_files(self.root, [bad.relative_to(self.root).as_posix()])

    def test_canonical_path_rejects_traversal(self):
        bad = self.manifest("bad.uados-manifest.json", [{"path": "../outside", "sha256": "0" * 64, "bytes": 0, "kind": "file"}])
        with self.assertRaises(UadosError):
            evidence_files(self.root, [bad.relative_to(self.root).as_posix()])

    def test_missing_snapshot_is_audit_error(self):
        self.write("leaf.bin", b"keep")
        root = self.manifest("root.uados-manifest.json", [self.entry("leaf.bin")])
        record = evidence_files(self.root, [root.relative_to(self.root).as_posix()])[0]
        (self.root / record["dependencies"][0]["snapshot"]).unlink()
        self.assertTrue(check_evidence(self.root, [record]))

    def test_mixed_batch_has_only_each_root_reachable_closure(self):
        self.write("leaf.bin", b"leaf")
        root = self.manifest("root.uados-manifest.json", [self.entry("leaf.bin")])
        self.write("ordinary.txt", b"ordinary")
        records = evidence_files(self.root, [root.relative_to(self.root).as_posix(), "ordinary.txt"])
        self.assertEqual([x["path"] for x in records[0]["dependencies"]], ["leaf.bin"])
        self.assertEqual(records[1]["path"], "ordinary.txt")

    def test_injected_cycle_guard_is_distinguished_from_hash_construction(self):
        root = self.write("cycle.uados-manifest.json", b"placeholder")
        raw_hash = hashlib.sha256(root.read_bytes()).hexdigest()
        injected = [{"path": "cycle.uados-manifest.json", "sha256": raw_hash, "bytes": len(root.read_bytes()), "kind": "manifest"}]
        with mock.patch("uados.manifests.parse", return_value=injected):
            with self.assertRaisesRegex(UadosError, "cycle"):
                evidence_files(self.root, ["cycle.uados-manifest.json"])

    def test_generated_and_alias_paths_are_rejected(self):
        self.write("leaf.bin", b"x")
        for path in ("PROJECT_MEMORY/session_reports/old.md", "CHANGE_REQUESTS/CR12.md", "leaf//x"):
            bad = self.manifest("bad-%s.uados-manifest.json" % len(path), [{"path": path, "sha256": "0" * 64, "bytes": 1, "kind": "file"}])
            with self.assertRaises(UadosError):
                evidence_files(self.root, [bad.relative_to(self.root).as_posix()])

    def test_plan_gate_audits_manifest_child_and_export_retains_it(self):
        self.write("leaf.bin", b"planned")
        root = self.manifest("plan.uados-manifest.json", [self.entry("leaf.bin")])
        report = self.project.start_session("Builder", "Codex")
        self.project.acknowledge(report["session"], report["report_hash"])
        task = self.project.add_task(report["session"], "Manifest task", "Keep closure", scopes=["leaf.bin"])["task"]
        governance.plan_task(self.project, report["session"], task, "Use closure", "Audit closure", [root.relative_to(self.root).as_posix()])
        record = self.project.read()[0]["tasks"][task]["plan"]["evidence"][0]
        self.write("leaf.bin", b"changed")
        self.assertTrue(self.project.audit()["errors"])
        destination = Path(self.tmp.name) / "export"
        with self.assertRaises(UadosError):
            self.project.export(destination)
        # Restore the live dependency; export then carries both root and leaf
        # snapshots, including the graph's historical bytes.
        self.write("leaf.bin", b"planned")
        self.project.export(destination)
        self.assertTrue((destination / record["snapshot"]).is_file())
        self.assertTrue((destination / record["dependencies"][0]["snapshot"]).is_file())
        (destination / ".uados/ledger.sqlite3").unlink()
        rebuilt = Project.rebuild_ledger(destination)
        self.assertTrue(rebuilt["rebuilt"])
        self.assertTrue(Project(destination).audit()["ok"])

        # A promised child snapshot is part of the historical closure.
        child_snapshot = destination / record["dependencies"][0]["snapshot"]
        child_snapshot.unlink()
        self.assertFalse(Project(destination).audit()["ok"])

    def test_bounds_and_malformed_stored_metadata_are_explicit(self):
        self.write("large.bin", b"012345")
        root = self.manifest("large.uados-manifest.json", [self.entry("large.bin")])
        from uados import manifests
        with mock.patch.object(manifests, "FILE_LIMIT", 4):
            with self.assertRaises(UadosError):
                evidence_files(self.root, [root.relative_to(self.root).as_posix()])
        self.write("leaf.bin", b"safe")
        good = self.manifest("good.uados-manifest.json", [self.entry("leaf.bin")])
        record = evidence_files(self.root, [good.relative_to(self.root).as_posix()])[0]
        forged = dict(record, manifest_version=True, dependencies=[dict(record["dependencies"][0], snapshot=["bad"])])
        from uados.manifests import validate_record
        self.assertTrue(validate_record(self.root, forged))
        forged_root = dict(record, kind="file", path="../forged.uados-manifest.json")
        self.assertTrue(validate_record(self.root, forged_root))

    def test_late_invalid_dependency_publishes_no_snapshots(self):
        self.write("good.bin", b"good")
        good = self.entry("good.bin")
        bad = {"path": "missing.bin", "sha256": "0" * 64, "bytes": 1, "kind": "file"}
        root = self.manifest("late.uados-manifest.json", [good, bad])
        before = sorted((self.root / ".uados/evidence/sha256").glob("*"))
        with self.assertRaises(UadosError):
            evidence_files(self.root, [root.relative_to(self.root).as_posix()])
        self.assertEqual(before, sorted((self.root / ".uados/evidence/sha256").glob("*")))


if __name__ == "__main__":
    unittest.main()
