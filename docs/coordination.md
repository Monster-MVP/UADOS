# Coordination boundary

`uados.coordination.MemoryLeaseBackend` is the reference semantics for future
coordination adapters. It serializes acquire, renew, release and validate
operations, assigns a per-resource monotonic fencing number, rejects stale or
incomplete tokens, expires at the exact `now >= expires_at` boundary and rejects
backward or non-finite injected clocks. The backend is process-local and uses no
ledger table or task schema.

```python
from uados.coordination import MemoryLeaseBackend

backend = MemoryLeaseBackend(clock=clock)
token = backend.acquire("project-A", "worker-1", 30)
backend.validate(token, resource="project-A", holder="worker-1")
token = backend.renew(token, 30)
backend.release(token)
```

The fencing number must be presented to the protected resource by a future
durable adapter. A local token does not authenticate its holder or prevent an
arbitrary process from bypassing the interface. Durable storage, cross-host
leases, crash recovery, clock synchronization, partition handling, remote
availability and fencing at the resource require separate reviewed adapters.

`coordination benchmark` reads and verifies the existing SQLite ledger while
holding the normal project lock, then reports event count, head hash, file sizes
and elapsed verification time. It never appends an event or rewrites a
projection:

```sh
python3 scripts/uados.py --project . coordination benchmark
```

The benchmark is a local history baseline. It does not establish a capacity,
distributed scheduling or hosted reliability claim.
