"""Tests for resilience backoff, error classification, and review bundle verification."""

import json
import tempfile
import unittest
from pathlib import Path
from typing import List

from uados.project import Project
from uados.resilience import (
    BackoffConfig,
    BundleInvalidError,
    BundleStaleError,
    PermanentError,
    RateLimitError,
    ResilienceError,
    ServiceUnavailableError,
    TransientError,
    calculate_delay,
    classify_error,
    create_review_bundle,
    retry_with_backoff,
    verify_review_bundle,
)
from uados.storage import safe_path


class ResilienceAndBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve() / "project"
        self.project = Project.initialize(self.root, "resilience-test", "test resilient review")

    def test_error_classification(self) -> None:
        ret, delay, cat = classify_error(RateLimitError("upstream rate limit hit"))
        self.assertTrue(ret)
        self.assertEqual(cat, "rate_limit")

        ret, delay, cat = classify_error(RuntimeError("HTTP 429 Too Many Requests: Retry-After: 12.5"))
        self.assertTrue(ret)
        self.assertEqual(delay, 12.5)
        self.assertEqual(cat, "rate_limit_429")

        ret, delay, cat = classify_error(ConnectionError("503 Service Unavailable: overloaded"))
        self.assertTrue(ret)
        self.assertEqual(cat, "transient_network")

        ret, delay, cat = classify_error(ValueError("invalid JSON syntax"))
        self.assertFalse(ret)
        self.assertIsNone(delay)
        self.assertEqual(cat, "permanent")

    def test_backoff_calculation_and_jitter(self) -> None:
        cfg_none = BackoffConfig(base_delay=1.0, max_delay=10.0, factor=2.0, jitter="none")
        self.assertEqual(calculate_delay(0, cfg_none), 1.0)
        self.assertEqual(calculate_delay(1, cfg_none), 2.0)
        self.assertEqual(calculate_delay(2, cfg_none), 4.0)
        self.assertEqual(calculate_delay(3, cfg_none), 8.0)
        self.assertEqual(calculate_delay(4, cfg_none), 10.0)  # Capped at max_delay

        cfg_equal = BackoffConfig(base_delay=2.0, max_delay=20.0, factor=2.0, jitter="equal")
        val_equal = calculate_delay(1, cfg_equal, prng=lambda: 0.5)
        self.assertEqual(val_equal, 2.0 + 0.5 * 2.0)

        cfg_full = BackoffConfig(base_delay=2.0, max_delay=20.0, factor=2.0, jitter="full")
        val_full = calculate_delay(1, cfg_full, prng=lambda: 0.25)
        self.assertEqual(val_full, 0.25 * 4.0)

    def test_retry_with_backoff_success_and_failure(self) -> None:
        attempts = 0
        slept: List[float] = []

        def succeed_on_third() -> str:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise RateLimitError("429 rate limit exceeded")
            return "success"

        cfg = BackoffConfig(base_delay=1.0, max_delay=10.0, factor=2.0, jitter="none", max_attempts=5)
        res = retry_with_backoff(
            succeed_on_third,
            config=cfg,
            sleep_fn=slept.append,
        )
        self.assertEqual(res, "success")
        self.assertEqual(attempts, 3)
        self.assertEqual(slept, [1.0, 2.0])

        # Exceed max attempts
        def always_fail() -> None:
            raise RateLimitError("persistent 429")

        with self.assertRaises(RateLimitError):
            retry_with_backoff(always_fail, config=BackoffConfig(max_attempts=3), sleep_fn=lambda _: None)

        # Permanent error fails immediately without retrying
        perm_attempts = 0

        def fail_permanent() -> None:
            nonlocal perm_attempts
            perm_attempts += 1
            raise ValueError("fatal syntax error")

        with self.assertRaises(PermanentError):
            retry_with_backoff(fail_permanent, config=BackoffConfig(max_attempts=3), sleep_fn=lambda _: None)
        self.assertEqual(perm_attempts, 1)

    def test_review_bundle_creation_and_strict_verification(self) -> None:
        session = self.project.start_session("DevAgent", "other")
        self.project.acknowledge(session["session"], session["report_hash"])

        src_file = self.root / "src" / "feature.py"
        src_file.parent.mkdir(parents=True, exist_ok=True)
        src_file.write_text("def hello() -> str:\n    return 'world'\n", encoding="utf-8")

        evidence_file = self.root / "evidence" / "plan.md"
        evidence_file.parent.mkdir(parents=True, exist_ok=True)
        evidence_file.write_text("# Plan\nImplement feature.\n", encoding="utf-8")

        task = self.project.add_task(
            session["session"],
            "Implement Feature X",
            "Must implement hello function and tests.",
            risk="routine",
            scopes=["src/feature.py"],
        )
        task_id = task["task"]

        from uados import governance as gov

        gov.plan_task(
            self.project,
            session["session"],
            task_id,
            "1. Implement hello",
            "1. Run tests",
            ["evidence/plan.md"],
        )

        bundle_path = "AUDIT/review-bundles/feature-x-bundle.json"
        bundle_info = create_review_bundle(
            self.project,
            session["session"],
            task_id,
            bundle_path,
            reason="upstream_rate_limit_429",
            test_command="python3 -m unittest",
        )
        self.assertEqual(bundle_info["task_id"], task_id)
        self.assertEqual(bundle_info["file_count"], 1)

        # Verify untouched bundle
        verify_res = verify_review_bundle(self.project, bundle_path)
        self.assertTrue(verify_res["verified"])
        self.assertEqual(verify_res["task_id"], task_id)
        self.assertEqual(verify_res["file_count"], 1)

        # Tamper target file by exactly 1 byte
        src_file.write_text("def hello() -> str:\n    return 'World'\n", encoding="utf-8")
        with self.assertRaises(BundleStaleError):
            verify_review_bundle(self.project, bundle_path)

        # Delete file
        src_file.unlink()
        with self.assertRaises(BundleStaleError):
            verify_review_bundle(self.project, bundle_path)

    def test_review_bundle_cli_integration(self) -> None:
        session = self.project.start_session("DevAgent", "other")
        self.project.acknowledge(session["session"], session["report_hash"])

        f = self.root / "module.py"
        f.write_text("X = 1\n", encoding="utf-8")
        plan_doc = self.root / "plan.md"
        plan_doc.write_text("Plan.\n", encoding="utf-8")

        task = self.project.add_task(
            session["session"],
            "Task Module",
            "Module description",
            risk="routine",
            scopes=["module.py"],
        )
        task_id = task["task"]

        from uados import governance as gov

        gov.plan_task(self.project, session["session"], task_id, "Steps", "Checks", ["plan.md"])

        from uados.cli import main

        out_bundle = "AUDIT/review-bundles/cli-test-bundle.json"
        import sys
        from io import StringIO

        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            exit_code = main([
                "--project", str(self.root),
                "review-bundle", "create", task_id,
                "--session", session["session"],
                "--output", out_bundle,
            ])
            self.assertIn(exit_code, (0, None))
            output_json = json.loads(sys.stdout.getvalue())
            self.assertEqual(output_json["task_id"], task_id)

            sys.stdout = StringIO()
            exit_code_verify = main([
                "--project", str(self.root),
                "review-bundle", "verify", out_bundle,
            ])
            self.assertIn(exit_code_verify, (0, None))
            verify_json = json.loads(sys.stdout.getvalue())
            self.assertTrue(verify_json["verified"])
        finally:
            sys.stdout = old_stdout


if __name__ == "__main__":
    unittest.main()
