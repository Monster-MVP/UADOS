import hashlib, json, sqlite3, sys
from pathlib import Path
sys.path.insert(0, '/Volumes/wdmonster/emonsterhome/Desktop/上海交通大学/agent-work/src')
from uados.context import context_bundle, render_views, report_markdown
from uados.protocol import all_evidence, current_evidence
from uados.storage import canonical, file_hash, snapshot_problems, scope_snapshot, now
from uados.project import Project, check_evidence

root = Path('/Volumes/wdmonster/emonsterhome/Desktop/上海交通大学/agent-work')
snapshot=Path('/tmp/uados-phase3-audit-snapshot-818')
db = snapshot/'ledger.sqlite3'; journal = snapshot/'events.jsonl'
result = {'ok': True, 'errors': [], 'warnings': [], 'event_count': 0,
          'procedure': 'Independent read-only streamed audit: verifies every full event hash/chain/state and exact projections; does not invoke or replace Project.mutate.',
          'governance_ok': False, 'governance_limit': 'Events 745-818 used an unreviewed temporary wrapper omitting full history/projection checks. Root authored or submitted reviewer acknowledgements/challenges/votes; D17/D18 are not evidence of actual independent three-round acceptance.',
          'started_at': now(), 'errors_scope': 'Current content, promised snapshots, every historical event and all projections'}
conn = sqlite3.connect(str(db)); conn.execute('PRAGMA query_only=ON')
print('starting SQLite quick_check', file=sys.stderr, flush=True)
if conn.execute('PRAGMA quick_check').fetchone()[0] != 'ok': result['errors'].append('SQLite quick_check failed')
print('quick_check complete; streaming events', file=sys.stderr, flush=True)
state = json.loads(conn.execute('SELECT value FROM state WHERE id=1').fetchone()[0])
headers=[]; previous='0'*64; last_state=None; line_count=0
history={}
record_key=lambda r:(r['path'],r['sha256'],r.get('snapshot'),canonical(r.get('dependencies',[])) if r.get('manifest_version') is not None else None)
with journal.open('rb') as stream:
    for seq, raw in conn.execute('SELECT sequence,value FROM events ORDER BY sequence'):
        event=json.loads(raw); claimed=event.pop('hash',None)
        if seq != event.get('sequence') or seq != result['event_count']+1: result['errors'].append(f'sequence {seq}')
        if event.get('previous_hash') != previous: result['errors'].append(f'previous hash {seq}')
        if hashlib.sha256(canonical(event).encode()).hexdigest() != claimed: result['errors'].append(f'event hash {seq}')
        event['hash']=claimed; previous=claimed; last_state=event.get('state'); result['event_count'] += 1
        for record in all_evidence(event['state']): history.setdefault(record_key(record),record)
        headers.append({k:event.get(k) for k in ('sequence','occurred_at','kind','actor','summary','previous_hash','hash')})
        line=stream.readline(); line_count += 1
        if line != (canonical(event)+'\n').encode(): result['errors'].append(f'journal mismatch {seq}')
        if seq % 100 == 0: print(f'verified event {seq}',file=sys.stderr,flush=True)
    if stream.readline(): result['errors'].append('journal has extra lines')
if line_count != result['event_count']: result['errors'].append(f'journal line count {line_count} != {result["event_count"]}')
if canonical(last_state) != canonical(state): result['errors'].append('SQLite state differs from final event')
state_bytes=json.dumps(state,indent=2,ensure_ascii=False,sort_keys=True)+'\n'
if (root/'.uados/state.json').read_text(encoding='utf-8') != state_bytes: result['errors'].append('state projection mismatch')
views=render_views(state,headers)
for rel, content in views.items():
    p=root/rel
    if not p.is_file() or p.read_text(encoding='utf-8') != content: result['errors'].append('view mismatch: '+rel)
for sess in state['sessions'].values():
    for report in sess['reports']:
        p=root/report['path']; expected=report_markdown(report['content'],report['hash'])
        if not p.is_file() or p.read_text(encoding='utf-8') != expected: result['errors'].append('report mismatch: '+report['path'])
for record in current_evidence(state):
    result['errors'].extend(snapshot_problems(root,record))
    p=root/record['path']
    if not p.is_file() or file_hash(p) != record['sha256']: result['errors'].append('current evidence mismatch: '+record['path'])
for task in state['tasks'].values():
    if task['status']=='done' and (not task['work'] or not task['evidence']): result['errors'].append('done task lacks work/evidence: '+task['id'])
    if task['status']=='done' and scope_snapshot(root,task['scope']) != task['submission_files']: result['warnings'].append('Completed task scope has changed since validation: '+task['id'])
active_keys={record_key(r) for r in current_evidence(state)}
historical_drift=[]; archived=[]
for key,record in history.items():
    result['errors'].extend(snapshot_problems(root,record))
    if record.get('manifest_version') is not None:
        from uados.manifests import validate_record
        result['errors'].extend(validate_record(root,record))
    if key in active_keys: continue
    changed=check_evidence(root,[record])
    if changed:
        finding={'path':record['path'],'sha256':record['sha256'],'snapshot':record.get('snapshot'),'problems':changed}
        if record.get('snapshot') and not snapshot_problems(root,record): archived.append(finding)
        else: historical_drift.append(finding)
result['history_ok']=not historical_drift
result['historical_evidence_drift']=historical_drift
result['archived_originals']=archived
result['evidence_records_checked']=len(history)
try: result['context_fingerprint']=context_bundle(root,state,headers)['fingerprint']
except Exception as exc: result['errors'].append('context check: '+str(exc))
project=Project(root)
for task in state['tasks'].values():
    result['errors'].extend(check_evidence(root,task['evidence']))
for decision in state['decisions']: result['errors'].extend(check_evidence(root,decision['evidence']))
for exp in state['experiments'].values():
    result['errors'].extend(check_evidence(root,[exp['config']]+exp['datasets']))
    for run in exp['runs']: result['errors'].extend(check_evidence(root,run.get('outputs',[])+run.get('analysis_evidence',[])))
result['head_hash']=previous; result['state_sha256']=hashlib.sha256(state_bytes.encode()).hexdigest(); result['line_count']=line_count
result['errors']=sorted(set(result['errors']));result['ok']=not result['errors'];result['ended_at']=now()
result['ledger_bytes']=db.stat().st_size;result['journal_bytes']=journal.stat().st_size
print(json.dumps(result,indent=2,ensure_ascii=False))
