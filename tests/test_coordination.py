import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from uados.coordination import (ClockError, CoordinationError, InvalidLeaseError,
                                LeaseBusyError, LeaseExpiredError,
                                MemoryLeaseBackend, StaleLeaseError,
                                benchmark_history)
from uados.project import Project


class FakeClock:
    def __init__(self, value=10.0):
        self.value = value

    def __call__(self):
        return self.value


class CoordinationTests(unittest.TestCase):
    def test_contention_expiry_takeover_and_monotonic_fencing(self):
        clock = FakeClock()
        backend = MemoryLeaseBackend(clock=clock)
        first = backend.acquire("resource", "one", 5)
        with self.assertRaises(LeaseBusyError):
            backend.acquire("resource", "two", 5)
        clock.value = 15.0
        second = backend.acquire("resource", "two", 5)
        self.assertGreater(second.fencing, first.fencing)
        with self.assertRaises(StaleLeaseError):
            backend.validate(first)

    def test_renew_release_and_exact_expiry(self):
        clock = FakeClock()
        backend = MemoryLeaseBackend(clock=clock)
        token = backend.acquire("r", "h", 5)
        clock.value = 14.999
        renewed = backend.renew(token, 5)
        self.assertEqual(renewed.fencing, token.fencing)
        with self.assertRaises(StaleLeaseError):
            backend.validate(token)
        backend.validate(renewed)
        clock.value = 20.0
        with self.assertRaises(LeaseExpiredError):
            backend.validate(renewed)
        with self.assertRaises(StaleLeaseError):
            backend.release(renewed)

    def test_clock_and_input_bounds_fail_closed(self):
        clock = FakeClock()
        backend = MemoryLeaseBackend(clock=clock)
        with self.assertRaises(InvalidLeaseError):
            backend.acquire("", "h", 1)
        with self.assertRaises(InvalidLeaseError):
            backend.acquire("r", "h", math.inf)
        with self.assertRaises(InvalidLeaseError):
            backend.acquire("r", "h", 10 ** 10000)
        backend.acquire("r", "h", 1)
        clock.value = 9.0
        with self.assertRaises(ClockError):
            backend.acquire("other", "h", 1)
        clock.value = math.nan
        with self.assertRaises(ClockError):
            backend.acquire("other", "h", 1)

    def test_resources_are_isolated_and_forged_tokens_fail(self):
        clock = FakeClock()
        backend = MemoryLeaseBackend(clock=clock)
        token = backend.acquire("r1", "h", 5)
        other = backend.acquire("r2", "h", 5)
        self.assertEqual(token.fencing, 1)
        self.assertEqual(other.fencing, 1)
        with self.assertRaises(StaleLeaseError):
            backend.validate(token, resource="r2")
        with self.assertRaises(InvalidLeaseError):
            backend.validate({"resource": "r1"})
        forged = type(token)(resource={}, holder=token.holder, fencing=token.fencing,  # type: ignore[arg-type]
                             issued_at=token.issued_at, expires_at=token.expires_at,
                             nonce=token.nonce, backend=token.backend)
        with self.assertRaises(InvalidLeaseError):
            backend.validate(forged)
        huge_time = type(token)(resource=token.resource, holder=token.holder, fencing=token.fencing,
                                issued_at=10 ** 10000, expires_at=token.expires_at,
                                nonce=token.nonce, backend=token.backend)
        with self.assertRaises(InvalidLeaseError):
            backend.validate(huge_time)

    def test_benchmark_is_read_only_and_cli_matches(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            project = Project.initialize(root, "coordination", "benchmark")
            before = project.read()[1][-1]["hash"]
            result = benchmark_history(project)
            self.assertFalse(result["ledger_mutated"])
            self.assertEqual(result["head_hash"], before)
            self.assertEqual(project.read()[1][-1]["hash"], before)
            env = dict(__import__("os").environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
            cli = subprocess.run([sys.executable, "-m", "uados", "--project", str(root), "coordination", "benchmark"],
                                 env=env, capture_output=True, text=True)
            self.assertEqual(cli.returncode, 0, cli.stderr)
            self.assertEqual(json.loads(cli.stdout)["head_hash"], before)

    def test_sqlite_uri_percent_encoding_and_missing_file_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "p#frag"
            project = Project.initialize(root, "uri", "test")
            before = project.read()[1][-1]["hash"]
            result = benchmark_history(project)
            self.assertFalse(result["ledger_mutated"])
            self.assertEqual(result["head_hash"], before)
            truncated_sibling = Path(temporary) / "p"
            self.assertFalse(truncated_sibling.exists())

            class FakeProject:
                root: Path
            fake = FakeProject()
            fake.root = Path(temporary) / "nonexistent"
            with self.assertRaises(CoordinationError):
                benchmark_history(fake)

    def test_max_ttl_cap_enforced_in_acquire_and_renew(self):
        clock = FakeClock(10.0)
        backend = MemoryLeaseBackend(clock=clock, max_ttl=5.0)
        with self.assertRaises(InvalidLeaseError):
            backend.acquire("r", "h", 5.01)
        with self.assertRaises(InvalidLeaseError):
            backend.acquire("r", "h", 60.0)
        token = backend.acquire("r", "h", 4.0)
        self.assertEqual(token.expires_at, 14.0)
        with self.assertRaises(InvalidLeaseError):
            backend.renew(token, 5.01)
        renewed = backend.renew(token, 5.0)
        self.assertEqual(renewed.expires_at, 15.0)

    def test_backend_instance_isolation_and_cross_instance_rejection(self):
        clock = FakeClock(10.0)
        backend_a = MemoryLeaseBackend(clock=clock)
        backend_b = MemoryLeaseBackend(clock=clock)
        token_a = backend_a.acquire("resource", "holder", 10.0)
        token_b = backend_b.acquire("resource", "holder", 10.0)
        self.assertNotEqual(token_a.backend, token_b.backend)
        self.assertNotEqual(token_a, token_b)
        with self.assertRaises(StaleLeaseError):
            backend_b.validate(token_a)
        with self.assertRaises(StaleLeaseError):
            backend_b.release(token_a)
        with self.assertRaises(StaleLeaseError):
            backend_a.validate(token_b)
        deterministic = MemoryLeaseBackend(clock=clock, instance_id="alpha")
        self.assertEqual(deterministic._backend, "uados.memory.v1.alpha")

    def test_extreme_clock_and_float_boundaries_pre_commit_atomicity(self):
        boolean_backend = MemoryLeaseBackend(clock=lambda: True)
        with self.assertRaises(ClockError):
            boolean_backend.acquire("r", "h", 1.0)

        huge_backend = MemoryLeaseBackend(clock=lambda: 1e308)
        with self.assertRaises(ClockError):
            huge_backend.acquire("r", "h", 1.0)
        self.assertEqual(len(huge_backend._fences), 0)
        self.assertEqual(len(huge_backend._active), 0)

        negative_backend = MemoryLeaseBackend(clock=lambda: -5.0)
        with self.assertRaises(ClockError):
            negative_backend.acquire("r", "h", 1.0)

    def test_symlink_directory_and_file_traversal_rejection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "proj"
            project = Project.initialize(root, "symlink", "test")
            # 1. Symlink ledger file
            target_ledger = root / ".uados" / "ledger.sqlite3"
            sym_project_root = Path(temporary) / "proj_sym_file"
            sym_project_root.mkdir()
            (sym_project_root / ".uados").mkdir()
            sym_ledger = sym_project_root / ".uados" / "ledger.sqlite3"
            sym_ledger.symlink_to(target_ledger)

            class FakeProject:
                root: Path
            fake = FakeProject()
            fake.root = sym_project_root
            with self.assertRaises(CoordinationError):
                benchmark_history(fake)

            # 2. Symlink .uados directory
            sym_dir_root = Path(temporary) / "proj_sym_dir"
            sym_dir_root.mkdir()
            (sym_dir_root / ".uados").symlink_to(root / ".uados")
            fake_dir = FakeProject()
            fake_dir.root = sym_dir_root
            with self.assertRaises(CoordinationError):
                benchmark_history(fake_dir)

    def test_renew_atomic_failure_preserves_existing_lease(self):
        clock = FakeClock(10.0)
        backend = MemoryLeaseBackend(clock=clock, max_ttl=5.0)
        token = backend.acquire("resource", "holder", 4.0)
        self.assertEqual(token.expires_at, 14.0)
        # Attempt renew with ttl > max_ttl -> InvalidLeaseError
        with self.assertRaises(InvalidLeaseError):
            backend.renew(token, 10.0)
        # Original lease must be 100% intact and validated
        validated = backend.validate(token)
        self.assertEqual(validated.expires_at, 14.0)
        self.assertEqual(validated.fencing, token.fencing)

        # Attempt renew with precision failure -> ClockError
        huge_clock = FakeClock(0.99e14)
        huge_backend = MemoryLeaseBackend(clock=huge_clock, max_ttl=200.0)
        huge_token = huge_backend.acquire("resource", "holder", 100.0)
        huge_clock.value = 0.99e14 + 10.0
        with self.assertRaises(ClockError):
            huge_backend.renew(huge_token, 0.001)
        # Verify active entry wasn't replaced with corrupted token
        validated_huge = huge_backend.validate(huge_token)
        self.assertEqual(validated_huge.expires_at, 0.99e14 + 100.0)

    def test_clock_precision_loss_ulp_rejection(self):
        # Near 1e14, float ULP is 0.015625. A ttl of 0.001 or 0.005 cannot be represented accurately
        clock = FakeClock(0.99e14)
        backend = MemoryLeaseBackend(clock=clock)
        with self.assertRaises(ClockError):
            backend.acquire("resource", "holder", 0.001)
        with self.assertRaises(ClockError):
            backend.acquire("resource", "holder", 0.005)
        # Clean state preserved
        self.assertEqual(len(backend._active), 0)
        self.assertEqual(len(backend._fences), 0)


if __name__ == "__main__":
    unittest.main()
