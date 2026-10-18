"""Adaptive backoff, transient error resilience, and cross-session review bundles."""

from dataclasses import dataclass
import hashlib
import json
import math
import random
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

from .storage import (
    UadosError,
    canonical,
    digest,
    file_hash,
    now,
    safe_path,
    scope_snapshot,
)

BUNDLE_FORMAT = "uados-review-bundle"
BUNDLE_VERSION = 1
MAX_BUNDLE_BYTES = 512 * 1024


class ResilienceError(UadosError):
    """Base error for resilient dispatch and rate-limit recovery."""


class TransientError(ResilienceError):
    """An error that may succeed upon retry."""


class RateLimitError(TransientError):
    """Upstream HTTP 429 or provider concurrency limit error."""


class ServiceUnavailableError(TransientError):
    """Upstream HTTP 503 or network connectivity drop error."""


class PermanentError(ResilienceError):
    """An error that cannot be resolved through retries."""


class BundleError(UadosError):
    """Base error for review bundle operations."""


class BundleStaleError(BundleError):
    """Target source file was modified or deleted since the bundle was issued."""


class BundleInvalidError(BundleError):
    """The review bundle format, version, or payload is malformed."""


@dataclass(frozen=True)
class BackoffConfig:
    """Deterministic configuration for exponential backoff with jitter."""

    base_delay: float = 1.0
    max_delay: float = 60.0
    factor: float = 2.0
    jitter: str = "full"  # "full", "equal", or "none"
    max_attempts: int = 5

    def __post_init__(self) -> None:
        if self.base_delay <= 0 or not math.isfinite(self.base_delay):
            raise ResilienceError("base_delay must be a positive finite float.")
        if self.max_delay < self.base_delay or not math.isfinite(self.max_delay):
            raise ResilienceError("max_delay must be >= base_delay.")
        if self.factor < 1.0 or not math.isfinite(self.factor):
            raise ResilienceError("factor must be >= 1.0.")
        if self.jitter not in {"full", "equal", "none"}:
            raise ResilienceError("jitter must be 'full', 'equal', or 'none'.")
        if self.max_attempts < 1:
            raise ResilienceError("max_attempts must be >= 1.")


def classify_error(exc: BaseException) -> Tuple[bool, Optional[float], str]:
    """Inspect an exception to determine retryability, retry-after delay, and category."""
    if isinstance(exc, RateLimitError):
        return True, None, "rate_limit"
    if isinstance(exc, (TransientError, ServiceUnavailableError, TimeoutError, ConnectionError)):
        return True, None, "transient_network"

    msg = str(exc).lower()
    retry_after: Optional[float] = None

    # Check for HTTP status codes and standard rate limit keywords
    if any(k in msg for k in ("429", "rate limit", "rate_limit", "quota exceeded", "resource_exhausted", "too many requests")):
        # Look for Retry-After: <seconds> pattern
        import re
        match = re.search(r"retry[-_]after[:=\s]+([0-9.]+)", msg)
        if match:
            try:
                parsed = float(match.group(1))
                if math.isfinite(parsed) and parsed >= 0:
                    retry_after = parsed
            except ValueError:
                pass
        return True, retry_after, "rate_limit_429"

    if any(k in msg for k in ("503", "service unavailable", "overloaded", "bad gateway", "502", "gateway timeout", "504")):
        return True, None, "service_unavailable_503"

    return False, None, "permanent"


def calculate_delay(attempt: int, config: BackoffConfig, prng: Optional[Callable[[], float]] = None) -> float:
    """Calculate the backoff delay for a given attempt index (0-indexed)."""
    rand = prng() if prng is not None else random.random()
    raw_delay = min(config.max_delay, config.base_delay * (config.factor ** attempt))

    if config.jitter == "none":
        return raw_delay
    if config.jitter == "equal":
        half = raw_delay / 2.0
        return half + (rand * half)
    # Default to "full" jitter
    return rand * raw_delay


def retry_with_backoff(
    func: Callable[[], Any],
    *,
    config: Optional[BackoffConfig] = None,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    clock: Optional[Callable[[], float]] = None,
    sleep_fn: Optional[Callable[[float], None]] = None,
    prng: Optional[Callable[[], float]] = None,
) -> Any:
    """Execute a callable with adaptive exponential backoff and jitter."""
    cfg = config or BackoffConfig()
    get_time = clock or time.monotonic
    sleep = sleep_fn or time.sleep

    attempts: List[Dict[str, Any]] = []
    for attempt in range(cfg.max_attempts):
        started_at = get_time()
        try:
            return func()
        except BaseException as exc:
            retryable = False
            category = "unknown"
            delay: Optional[float] = None

            if retryable_exceptions and isinstance(exc, retryable_exceptions):
                retryable = True
                category = "explicit_retryable"
            else:
                is_ret, explicit_delay, category = classify_error(exc)
                if is_ret:
                    retryable = True
                    delay = explicit_delay

            if not retryable or attempt + 1 >= cfg.max_attempts:
                if isinstance(exc, ResilienceError):
                    raise
                if category.startswith("rate_limit"):
                    raise RateLimitError(f"Rate limit retry exhausted after {attempt + 1} attempts: {exc}") from exc
                if retryable:
                    raise TransientError(f"Transient error retry exhausted after {attempt + 1} attempts: {exc}") from exc
                raise PermanentError(f"Non-retryable failure: {exc}") from exc

            if delay is None:
                delay = calculate_delay(attempt, cfg, prng=prng)

            attempts.append({
                "attempt": attempt + 1,
                "category": category,
                "delay": delay,
                "error": str(exc),
                "timestamp": started_at,
            })
            sleep(delay)

    raise ResilienceError("Retry loop terminated unexpectedly.")


def create_review_bundle(
    project: Any,
    session_id: str,
    task_id: str,
    output_path: str,
    reason: str = "upstream_rate_limit_429",
    test_command: str = "python3 -m unittest discover -s tests",
) -> Dict[str, Any]:
    """Generate a deterministic review bundle for offline/cross-session inspection."""
    state, events, _ = project.read(strict=True)
    task = project._task(state, task_id)
    scope: List[str] = list(task.get("scope", []))
    if not scope:
        raise BundleInvalidError(f"Task {task_id} has no declared scope files to review.")

    snapshot = scope_snapshot(project.root, scope)
    file_hashes: Dict[str, str] = {}
    for rel_path, digest_val in sorted(snapshot.items()):
        if digest_val == "missing":
            raise BundleInvalidError(f"Declared scope path is missing: {rel_path}")
        file_hashes[rel_path] = digest_val

    if not file_hashes:
        raise BundleInvalidError(f"Task {task_id} scope contains no reviewable files.")

    bundle_id = "RB-" + hashlib.sha256(f"{task_id}:{now()}:{session_id}".encode("utf-8")).hexdigest()[:16]

    bundle_data: Dict[str, Any] = {
        "format": BUNDLE_FORMAT,
        "version": BUNDLE_VERSION,
        "bundle_id": bundle_id,
        "task_id": task_id,
        "task_title": task["title"],
        "task_risk": task["risk"],
        "created_at": now(),
        "created_by_session": session_id,
        "reason": reason,
        "test_command": test_command,
        "target_scope": sorted(scope),
        "file_hashes": file_hashes,
        "plan_snapshot": task.get("plan"),
        "role_plan_id": task.get("role_plan"),
        "review_templates": {
            "stage1_analysis": {
                "solution": "Clear architectural evaluation of the submitted work",
                "assumptions": ["List verified operating conditions and resource assumptions"],
                "risks": ["List concrete edge cases and failure modes"],
                "alternatives": ["Identify alternative implementations considered"],
                "evidence": ["Path to local evidence artifact demonstrating analysis"],
            },
            "stage2_challenge": {
                "target": "Specific module or interface challenged",
                "failure": "Concrete execution trace or parameter boundary leading to failure",
                "unsupported": "Contract violation or unvalidated assumption",
                "alternative": "Safer or more robust design pattern",
                "missing_evidence": "Missing test case or metric assertion",
                "evidence": ["Path to reproducible challenge evidence"],
            },
            "stage3_consensus": {
                "select": "Approved implementation path",
                "verdict": "approve",
                "reason": "Comprehensive rationale for independent approval",
                "evidence": ["Path to final validation artifact"],
            },
        },
    }

    out_target = safe_path(project.root, output_path, allow_missing=True)
    out_target.parent.mkdir(parents=True, exist_ok=True)
    raw_content = canonical(bundle_data) + "\n"
    if len(raw_content.encode("utf-8")) > MAX_BUNDLE_BYTES:
        raise BundleInvalidError(f"Review bundle exceeds maximum allowed size ({MAX_BUNDLE_BYTES} bytes).")

    out_target.write_text(raw_content, encoding="utf-8")
    return {
        "bundle_id": bundle_id,
        "task_id": task_id,
        "output_path": str(out_target.relative_to(project.root)),
        "file_count": len(file_hashes),
        "created_at": bundle_data["created_at"],
        "reason": reason,
    }


def verify_review_bundle(project: Any, bundle_path: str) -> Dict[str, Any]:
    """Verify that a review bundle is syntactically valid and that all target files match their exact SHA-256."""
    target_path = safe_path(project.root, bundle_path, allow_missing=False)
    if not target_path.is_file():
        raise BundleInvalidError(f"Review bundle path is not a file: {bundle_path}")

    try:
        content = target_path.read_text(encoding="utf-8")
        data = json.loads(content)
    except Exception as exc:
        raise BundleInvalidError(f"Review bundle is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise BundleInvalidError("Review bundle payload must be a JSON object.")

    if data.get("format") != BUNDLE_FORMAT or data.get("version") != BUNDLE_VERSION:
        raise BundleInvalidError(f"Unsupported bundle format ({data.get('format')}) or version ({data.get('version')}).")

    required_fields = {"format", "version", "bundle_id", "task_id", "created_at", "target_scope", "file_hashes"}
    if not required_fields.issubset(set(data.keys())):
        missing = required_fields - set(data.keys())
        raise BundleInvalidError(f"Review bundle is missing required fields: {missing}")

    file_hashes = data["file_hashes"]
    if not isinstance(file_hashes, dict):
        raise BundleInvalidError("file_hashes field must be a dictionary.")

    mismatches: List[Dict[str, str]] = []
    missing_files: List[str] = []

    for rel_path, expected_hash in file_hashes.items():
        try:
            current_file = safe_path(project.root, rel_path, allow_missing=False)
            current_hash = file_hash(current_file)
            if current_hash != expected_hash:
                mismatches.append({
                    "path": rel_path,
                    "expected_sha256": expected_hash,
                    "actual_sha256": current_hash,
                })
        except UadosError:
            missing_files.append(rel_path)

    if missing_files or mismatches:
        details = []
        if missing_files:
            details.append(f"Missing files: {missing_files}")
        if mismatches:
            details.append(f"Hash mismatches: {mismatches}")
        raise BundleStaleError(
            f"Review bundle {data.get('bundle_id')} is stale or target files tampered: {'; '.join(details)}"
        )

    return {
        "verified": True,
        "bundle_id": data["bundle_id"],
        "task_id": data["task_id"],
        "file_count": len(file_hashes),
        "target_scope": data["target_scope"],
        "status": "active_and_valid",
        "verified_at": now(),
    }
