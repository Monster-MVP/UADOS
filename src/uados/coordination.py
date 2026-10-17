"""Additive lease and fencing boundary for future coordination backends.

The reference backend is deliberately process-local.  It defines semantics for
future durable or remote implementations without changing the UADOS ledger.
"""

from dataclasses import dataclass
import math
import secrets
import sqlite3
import threading
import time
from pathlib import Path

from .storage import (UadosError, connect, load_ledger, project_lock,
                     streaming_load_ledger)


MAX_TEXT = 256
MAX_TTL = 24 * 60 * 60.0


class CoordinationError(UadosError):
    """A lease contract violation."""


class LeaseBusyError(CoordinationError):
    """The resource has a live owner."""


class LeaseExpiredError(CoordinationError):
    """The lease reached its exclusive expiry boundary."""


class StaleLeaseError(CoordinationError):
    """The token no longer names the current fenced owner."""


class InvalidLeaseError(CoordinationError):
    """The lease input is malformed or unbounded."""


class ClockError(CoordinationError):
    """The injected clock moved backwards or returned a non-finite value."""


@dataclass(frozen=True)
class LeaseToken:
    resource: str
    holder: str
    fencing: int
    issued_at: float
    expires_at: float
    nonce: str
    backend: str


class LeaseBackend:
    """Interface future durable/remote coordination backends must implement."""

    def acquire(self, resource, holder, ttl_seconds):
        raise NotImplementedError

    def renew(self, token, ttl_seconds):
        raise NotImplementedError

    def release(self, token):
        raise NotImplementedError

    def validate(self, token, resource=None, holder=None):
        raise NotImplementedError


class MemoryLeaseBackend(LeaseBackend):
    """Serialized, deterministic reference semantics; no durable coordination."""

    def __init__(self, clock=None, max_ttl=MAX_TTL, instance_id=None):
        self._clock = clock or time.monotonic
        self._max_ttl = self._ttl(max_ttl)
        self._last_now = None
        self._fences = {}
        self._active = {}
        self._lock = threading.RLock()
        if instance_id is not None:
            self._instance_id = self._text(instance_id, "instance_id")
        else:
            self._instance_id = secrets.token_hex(8)
        self._backend = "uados.memory.v1.%s" % self._instance_id

    @staticmethod
    def _text(value, label):
        if not isinstance(value, str) or not value or len(value) > MAX_TEXT:
            raise InvalidLeaseError("Lease %s must be a bounded nonempty string." % label)
        return value

    @staticmethod
    def _ttl(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise InvalidLeaseError("Lease TTL must be a finite positive number.")
        try:
            value = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise InvalidLeaseError("Lease TTL must be finite, positive and bounded.") from exc
        if not math.isfinite(value) or value <= 0 or value > MAX_TTL:
            raise InvalidLeaseError("Lease TTL must be finite, positive and bounded.")
        return value

    def _validate_ttl(self, value):
        ttl = self._ttl(value)
        if ttl > self._max_ttl:
            raise InvalidLeaseError("Lease TTL must not exceed configured backend maximum.")
        return ttl

    @staticmethod
    def _finite_number(value, label):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise InvalidLeaseError("Lease %s must be a finite number." % label)
        try:
            result = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise InvalidLeaseError("Lease %s must be a finite number." % label) from exc
        if not math.isfinite(result):
            raise InvalidLeaseError("Lease %s must be a finite number." % label)
        return result

    def _observe(self):
        try:
            raw = self._clock()
        except (TypeError, ValueError, OverflowError) as exc:
            raise ClockError("Lease clock must return a finite number.") from exc
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise ClockError("Lease clock must return a finite number.")
        try:
            value = float(raw)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ClockError("Lease clock must return a finite number.") from exc
        if not math.isfinite(value) or value < 0 or value > 1e14:
            raise ClockError("Lease clock must be finite, non-negative and within representable bounds.")
        if self._last_now is not None and value < self._last_now:
            raise ClockError("Lease clock must be finite and monotonic.")
        self._last_now = value
        return value

    def _complete(self, token):
        if not isinstance(token, LeaseToken):
            raise InvalidLeaseError("Lease token must be a complete LeaseToken.")
        self._text(token.resource, "resource")
        self._text(token.holder, "holder")
        self._text(token.nonce, "nonce")
        self._text(token.backend, "backend")
        if (not isinstance(token.fencing, int) or isinstance(token.fencing, bool) or token.fencing <= 0
                or self._finite_number(token.issued_at, "issued_at") is None
                or self._finite_number(token.expires_at, "expires_at") is None):
            raise InvalidLeaseError("Lease token fields are invalid or incomplete.")

    def _new_token(self, resource, holder, fencing, issued, expires):
        # The nonce is only an accidental-replay guard; it is not authentication.
        nonce = "%s:%d:%0.9f" % (self._backend, fencing, issued)
        return LeaseToken(resource, holder, fencing, issued, expires, nonce, self._backend)

    def acquire(self, resource, holder, ttl_seconds):
        resource = self._text(resource, "resource")
        holder = self._text(holder, "holder")
        ttl = self._validate_ttl(ttl_seconds)
        with self._lock:
            current = self._observe()
            active = self._active.get(resource)
            if active is not None and current < active.expires_at:
                raise LeaseBusyError("Lease resource is held by another live token.")
            expires = current + ttl
            if not (expires > current and math.isfinite(expires)):
                raise ClockError("Lease expiry calculation failed representable precision bounds.")
            if not math.isclose(expires - current, ttl, rel_tol=1e-7, abs_tol=1e-4):
                raise ClockError("Lease clock precision loss: requested TTL cannot be represented accurately at current clock value.")
            fencing = self._fences.get(resource, 0) + 1
            token = self._new_token(resource, holder, fencing, current, expires)
            self._complete(token)
            self._fences[resource] = fencing
            self._active[resource] = token
            return token

    def _current(self, token: LeaseToken) -> LeaseToken:
        self._complete(token)
        if token.backend != self._backend:
            raise StaleLeaseError("Lease token belongs to another backend.")
        current = self._active.get(token.resource)
        if current is None or current != token:
            raise StaleLeaseError("Lease token is stale or was released.")
        return current

    def validate(self, token, resource=None, holder=None):
        with self._lock:
            current = self._observe()
            token = self._current(token)
            if current >= token.expires_at:
                self._active.pop(token.resource, None)
                raise LeaseExpiredError("Lease token reached its expiry boundary.")
            if resource is not None and resource != token.resource:
                raise StaleLeaseError("Lease resource does not match the token.")
            if holder is not None and holder != token.holder:
                raise StaleLeaseError("Lease holder does not match the token.")
            return token

    def renew(self, token, ttl_seconds):
        ttl = self._validate_ttl(ttl_seconds)
        with self._lock:
            current = self._observe()
            token = self._current(token)
            if current >= token.expires_at:
                self._active.pop(token.resource, None)
                raise LeaseExpiredError("Expired leases cannot be renewed.")
            expires = current + ttl
            if not (expires > current and math.isfinite(expires)):
                raise ClockError("Lease expiry calculation failed representable precision bounds.")
            if not math.isclose(expires - current, ttl, rel_tol=1e-7, abs_tol=1e-4):
                raise ClockError("Lease clock precision loss: requested TTL cannot be represented accurately at current clock value.")
            renewed = self._new_token(token.resource, token.holder, token.fencing, token.issued_at, expires)
            self._complete(renewed)
            self._active[token.resource] = renewed
            return renewed

    def release(self, token):
        with self._lock:
            current = self._observe()
            token = self._current(token)
            if current >= token.expires_at:
                self._active.pop(token.resource, None)
                raise LeaseExpiredError("Expired leases cannot be released as live ownership.")
            del self._active[token.resource]
            return {"released": True, "resource": token.resource, "fencing": token.fencing}


def benchmark_history(project):
    """Measure the current local history without appending an event or projection."""
    started = time.perf_counter()
    root = Path(project.root)
    uados_dir = root / ".uados"
    ledger = uados_dir / "ledger.sqlite3"
    state_projection = uados_dir / "state.json"
    events_projection = uados_dir / "events.jsonl"

    def _verify_safe_paths():
        if uados_dir.is_symlink():
            raise CoordinationError("The .uados directory must not be a symlink.")
        if ledger.is_symlink():
            raise CoordinationError("The ledger must not be a symlink.")
        if not ledger.is_file():
            raise CoordinationError("The ledger file does not exist or is not a regular file.")

    _verify_safe_paths()
    with project_lock(root):
        _verify_safe_paths()
        uri = ledger.resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=30)
        try:
            state, events = streaming_load_ledger(connection, keep_events=False)
        finally:
            connection.close()
        ledger_bytes = ledger.stat().st_size
        state_bytes = state_projection.stat().st_size if state_projection.is_file() else 0
        events_bytes = events_projection.stat().st_size if events_projection.is_file() else 0
    elapsed = (time.perf_counter() - started) * 1000.0
    return {
        "backend": "sqlite-local-readonly",
        "event_count": len(events),
        "head_hash": events[-1]["hash"],
        "ledger_bytes": ledger_bytes,
        "state_projection_bytes": state_bytes,
        "events_projection_bytes": events_bytes,
        "verify_milliseconds": round(elapsed, 3),
        "ledger_mutated": False,
        "claim_limit": "Local read-only size/timing baseline; no cross-host coordination or scale guarantee."
    }
