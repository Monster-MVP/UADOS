# Phase 3 coordination boundary plan (T000010)

## Bounded outcome

Introduce an additive coordination boundary that makes lease ownership, expiry,
renewal and fencing semantics executable without changing the existing SQLite
ledger schema or task lifecycle. The reference backend is an injectable local
state machine for deterministic tests. A read-only benchmark reports current
SQLite history size and verification timing so a future remote backend can be
compared against a known local baseline.

## Contract and safety

The backend interface exposes acquire, renew, release and validate operations.
Every issued lease carries a resource, holder, monotonically increasing fencing
number and bounded expiry observation. A stale holder or stale fencing number
must fail before a protected operation is accepted. Expiry is evaluated through
an injected clock; tests never sleep. The reference backend is process-local and
does not claim cross-host coordination, durable fencing, authenticated identity,
network partition handling or clock synchronization.

The benchmark is read-only: it measures the existing ledger and projections,
does not append events, and reports limits when the local project is unavailable.
No remote service, schema migration, lock replacement or automatic task-lease
integration is included in this task.

## Validation and recovery

Exercise acquire contention, expiry takeover, renewal, release, stale-token
fencing, resource isolation, malformed TTL/holder/resource inputs and clock
boundaries. Verify repeated benchmark runs do not change the ledger head or
event count. Run the full suite, coordination-focused tests, scaffold check and
the normal audit. Preserve any failed probe as versioned evidence.

## Alternatives

Keep the current cooperative local task leases unchanged; add a remote service
before defining a stable interface; or modify the SQLite authority directly.
Choose the additive local state-machine contract plus read-only benchmark so
future distributed adapters have explicit semantics without weakening the
validated local authority.
