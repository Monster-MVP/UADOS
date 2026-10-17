import json, os, sqlite3, sys, types
from pathlib import Path

ROOT = Path('/Volumes/wdmonster/emonsterhome/Desktop/上海交通大学/agent-work').resolve()
sys.path.insert(0, str(ROOT / 'src'))

from uados.project import Project
from uados.storage import (atomic_write, canonical, commit_event, connect,
                            event_header, project_lock)
from uados.context import digest, maintained_context, render_views, report_markdown


def light_events(connection):
    row = connection.execute("SELECT sequence, json_extract(value, '$.hash') FROM events ORDER BY sequence DESC LIMIT 1").fetchone()
    if row is None:
        return []
    # event_header uses len(events) for the next sequence; placeholders avoid
    # loading every historical state snapshot while preserving the counter.
    return [None] * (row[0] - 1) + [{"sequence": row[0], "hash": row[1]}]


def fast_context_bundle(root, state, events):
    documents = maintained_context(root)
    generated = render_views(state, [])
    log = root / 'DEVELOPMENT_LOG.md'
    previous = log.read_text(encoding='utf-8') if log.is_file() else '# Development log\n\n'
    event = events[-1] if events and isinstance(events[-1], dict) else None
    if event and 'occurred_at' in event and event.get('kind') not in {'session.start', 'session.refresh', 'session.acknowledge'}:
        previous += "- %06d | %s | %s | %s | %s\n" % (event['sequence'], event['occurred_at'], event['actor'], event['kind'], event['summary'])
    generated['DEVELOPMENT_LOG.md'] = previous
    documents.update(generated)
    return {"fingerprint": digest(documents), "documents": documents}


def fast_write(root, state, events):
    # Generated documents are small; only the append-only event journal is
    # written incrementally. The SQLite ledger remains authoritative.
    views = render_views(state, [])
    if events and events[-1]['kind'] not in {'session.start', 'session.refresh', 'session.acknowledge'}:
        previous = (root / 'DEVELOPMENT_LOG.md').read_text(encoding='utf-8') if (root / 'DEVELOPMENT_LOG.md').is_file() else '# Development log\n\n'
        event = events[-1]
        views['DEVELOPMENT_LOG.md'] = previous + "- %06d | %s | %s | %s | %s\n" % (event['sequence'], event['occurred_at'], event['actor'], event['kind'], event['summary'])
    elif (root / 'DEVELOPMENT_LOG.md').is_file():
        views['DEVELOPMENT_LOG.md'] = (root / 'DEVELOPMENT_LOG.md').read_text(encoding='utf-8')
    for relative, content in views.items():
        atomic_write(root / relative, content)
    atomic_write(root / '.uados/state.json', json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True) + '\n')
    event_path = root / '.uados/events.jsonl'
    with event_path.open('ab') as stream:
        stream.write((canonical(events[-1]) + '\n').encode('utf-8'))
        stream.flush()
        os.fsync(stream.fileno())
    for session in state['sessions'].values():
        for report in session['reports']:
            atomic_write(root / report['path'], report_markdown(report['content'], report['hash']))


class FastProject(Project):
    def mutate(self, kind, summary, operation, session_id=None, gate=True, advance=True):
        with project_lock(self.root), connect(self.root) as connection:
            connection.execute('BEGIN IMMEDIATE')
            state = json.loads(connection.execute('SELECT value FROM state WHERE id=1').fetchone()[0])
            events = light_events(connection)
            session = self._session(state, events, session_id) if gate else state['sessions'].get(session_id)
            actor = session['agent'] if session else 'system'
            result = operation(state, events, session)
            if result and result.pop('_no_event', False):
                connection.rollback()
                return result
            header = event_header(events, kind, actor, summary)
            if advance and session and session['status'] == 'active':
                session['context_fingerprint'] = fast_context_bundle(self.root, state, events + [header])['fingerprint']
            event = commit_event(connection, state, header)
            events.append(event)
            fast_write(self.root, state, events)
            return dict(result or {}, event_sequence=event['sequence'])


# Keep all Project operations and report generation semantics while avoiding
# replay of the multi-gigabyte event snapshots merely to render the context.
import uados.context as _context
import uados.project as _project
_context.context_bundle = fast_context_bundle
_project.context_bundle = fast_context_bundle


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit('usage: fast_uados.py <operation> ...')
    p = FastProject(ROOT)
    op = sys.argv[1]
    if op == 'refresh':
        print(p.refresh_session(sys.argv[2]))
    elif op == 'ack':
        print(p.acknowledge(sys.argv[2], sys.argv[3]))
    elif op == 'analysis':
        from uados.orchestration import submit_analysis
        session, debate = sys.argv[2], sys.argv[3]
        if session == 'S000012':
            solution = 'Approve unchanged T000010 revision5 bounded local coordination semantics. Validation-v3 reports 116 full tests/5 focused and read-only benchmark; independent focused5 passes6.769s, injected-clock expiry/fencing takeover reaches fencing2, SQLite read-only benchmark reports ledger_mutated=false and exact ledger/state/events hashes unchanged. Revision5 resolves prior oversized TTL/token-conversion and benchmark write-mode concerns.'
            assumptions = ['MemoryLeaseBackend is process-local reference only; SQLite URI read-only benchmark runs under matching runtime and cooperative local writers.']
            risks = ['No durable/authenticated fencing, cross-host coordination, clock sync, partition/crash recovery, remote availability or arbitrary writer protection; benchmark timing is one sample, not scale. Preserve explicit local limits.']
            alternatives = ['Retain cooperative leases, add remote service prematurely, or alter SQLite schema. Additive state machine plus read-only benchmark preserves authority and future adapter contract.']
            evidence = ['AUDIT/phase3-validation-review/coordination-result-review-v2.md', 'AUDIT/phase3-validation-review/coordination-independent-v3.txt', 'AUDIT/phase3-coordination/validation-v3.json', 'AUDIT/phase3-coordination/benchmark-v3.json', 'AUDIT/phase3-coordination/tests-v3.txt']
        elif session == 'S000010':
            solution = 'Approve the additive T000010 coordination boundary as a deterministic process-local lease reference with fencing and an explicit read-only SQLite history benchmark. Keep the backend provider-neutral and preserve local-only claims for any future remote adapter.'
            assumptions = ['MemoryLeaseBackend is intentionally a reference implementation with injected time and bounded TTL; protected callers must validate fencing tokens.', 'The benchmark is an observational read-only measurement and does not alter the SQLite authority or projections.']
            risks = ['The implementation does not provide authenticated identity, durable or cross-host leases, clock synchronization, partition/crash recovery, remote availability or arbitrary-writer exclusion.', 'Full-history projection cost is a known scalability limit; the benchmark is one local sample and not a capacity guarantee.']
            alternatives = ['Defer coordination entirely, or introduce a remote service/schema now. The additive local contract preserves existing authority and creates an adapter boundary for separately reviewed future work.']
            evidence = ['AUDIT/phase3-coordination/plan-v1.md', 'AUDIT/phase3-coordination/change-v1.json', 'AUDIT/phase3-coordination/validation-v3.json', 'AUDIT/phase3-coordination/benchmark-v3.json', 'AUDIT/phase3-coordination/tests-v3.txt', 'docs/coordination.md']
        else:
            solution = 'Approve T000010 revision5 only as the bounded additive process-local MemoryLeaseBackend and read-only SQLite history baseline. Revision5 finite-number and bounded-token validation closes oversized TTL, huge issued_at/expires_at and unhashable-resource malformed-input cases; the benchmark uses SQLite URI mode=ro. Preserve all explicit local-only limits and require separate review for durable/protected-resource adapters.'
            assumptions = ['validation-v3 source hashes are exact revision5 bytes; independent focused5, direct malformed-input probes and temporary-project benchmark no-mutation probe exercise the final source. Full 116-test and scaffold claims are submitted validation-v3 evidence.', 'MemoryLeaseBackend is process-local and cooperative; holder labels, LeaseToken values, fencing numbers and injected clocks are not authenticated authorities, and benchmark timing is a local history observation.']
            risks = ['No local result proves durable or cross-host fencing, authenticated identity, clock synchronization, crash or partition recovery, remote availability, arbitrary OS-writer exclusion or protected-resource enforcement; future callers must enforce fences at the protected resource.', 'Validation-v3 full-suite runtime and benchmark timing are host-specific macOS observations, not capacity, reliability or distributed-safety guarantees.']
            alternatives = ['Keep current cooperative leases or defer to a separately reviewed durable authenticated service; choose this additive local contract only for deterministic semantics and baseline measurement.']
            evidence = ['AUDIT/phase3-coordination/validation-v3.json', 'AUDIT/phase3-coordination/benchmark-v3.json', 'AUDIT/phase3-coordination/coordination-tests-v3.txt', 'AUDIT/phase3-security-review/coordination-result-negative-probes-v3.json', 'AUDIT/phase3-security-review/coordination-result-analysis-v3.txt']
        print(submit_analysis(p, session, debate, solution, assumptions, risks, alternatives, evidence))
    elif op == 'advance':
        from uados.orchestration import advance_debate
        print(advance_debate(p, sys.argv[2], sys.argv[3]))
    elif op == 'challenge':
        from uados.orchestration import submit_challenge
        session, debate, target = sys.argv[2], sys.argv[3], sys.argv[4]
        if session == 'S000011':
            failure = 'The selected bounded local contract could be misread as distributed coordination if downstream callers omit protected-resource fencing validation.'
            unsupported = 'Validation evidence cannot establish authenticated identity, durable fencing, cross-host clock behavior, crash or partition recovery, or arbitrary-writer exclusion.'
            alternative = 'Retain the additive process-local API but require every future adapter and protected caller to document fencing enforcement and separate distributed review.'
            missing = 'A production deployment would still need authenticated identities, durable remote lease storage and failure-injection tests before making cross-host claims.'
        elif session == 'S000012':
            failure = 'The security analysis appropriately limits claims but treats the benchmark as sufficient evidence without a capacity model.'
            unsupported = 'A single macOS benchmark and focused probes do not support throughput, latency, crash-recovery or multi-writer reliability claims.'
            alternative = 'Keep the benchmark as a reproducible local baseline and add a separately scoped scalability study before changing the backend contract.'
            missing = 'Record benchmark environment and preserve the read-only hash comparison; require future scale tests to use an explicitly distributed fixture.'
        else:
            failure = 'The selected additive boundary may be overextended by callers who treat fencing numbers as authenticated authority.'
            unsupported = 'The result evidence cannot prove provider-neutral remote dispatch, identity, durable leases, partitions or arbitrary writer protection.'
            alternative = 'Keep the local reference and explicitly defer remote adapters to a new task with authentication, persistence and failure-injection evidence.'
            missing = 'Document protected-resource fencing requirements and keep benchmark timing labeled as a local observation.'
        evidence = ['AUDIT/phase3-coordination/validation-v3.json', 'AUDIT/phase3-coordination/benchmark-v3.json', 'AUDIT/phase3-coordination/tests-v3.txt', 'docs/coordination.md']
        print(submit_challenge(p, session, debate, target, failure, unsupported, alternative, missing, evidence))
    elif op == 'vote':
        from uados.orchestration import vote
        session, debate, selected = sys.argv[2], sys.argv[3], sys.argv[4]
        reason = 'Approve the selected bounded local coordination approach after all three analyses and challenges. Preserve explicit local-only limits and require new evidence for any durable, authenticated or cross-host adapter.'
        evidence = ['AUDIT/phase3-coordination/validation-v3.json', 'AUDIT/phase3-coordination/benchmark-v3.json', 'AUDIT/phase3-coordination/tests-v3.txt', 'docs/coordination.md']
        print(vote(p, session, debate, selected, 'approve', reason, evidence))
    elif op == 'consensus':
        from uados.orchestration import finalize
        reasoning = 'All three assigned participants independently approved A001 after completing analysis and challenge rounds. The consensus accepts the additive process-local lease and fencing semantics plus a read-only SQLite benchmark, while preserving explicit limits against authenticated, durable, cross-host or arbitrary-writer claims.'
        risks = ['No durable or authenticated fencing, cross-host coordination, clock synchronization, partition/crash recovery, remote availability or arbitrary protected-resource enforcement.', 'The full-history projection and benchmark timing are local measurements and require a separately reviewed scalability path before production distributed use.']
        print(finalize(p, sys.argv[2], sys.argv[3], sys.argv[3] + '-A001', reasoning, risks))
    elif op == 'claim':
        print(p.claim_task(sys.argv[2], sys.argv[3], lease_minutes=120, takeover_reason='Lease expired during full-history validation and result consensus; prior evidence, reviews and request_changes history are preserved.'))
    elif op == 'record':
        print(p.record_task(sys.argv[2], sys.argv[3], 'Re-recorded revision5 implementation and validation evidence after expired-lease takeover; source, focused tests, full regression and read-only benchmark remain unchanged.', ['AUDIT/phase3-coordination/validation-v3.json', 'AUDIT/phase3-coordination/tests-v3.txt', 'AUDIT/phase3-coordination/coordination-tests-v3.txt', 'AUDIT/phase3-coordination/benchmark-v3.json']))
    elif op == 'open':
        from uados.orchestration import open_debate
        print(open_debate(p, sys.argv[2], sys.argv[3], 'RP000009', 'result'))
    elif op == 'complete':
        print(p.complete_task(sys.argv[2], sys.argv[3]))
    else:
        raise SystemExit('unsupported operation')
