"""Read-only independent final acceptance verification; no nested-enforcement claim."""
import hashlib,json,platform,sys,zipfile
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root/'src'))
from uados.project import Project,check_evidence
from uados.storage import scope_snapshot

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def records_valid(records):
    return [{'path':r['path'],'ok':(root/r['path']).is_file() and sha(root/r['path'])==r['sha256'] and (root/r['path']).stat().st_size==r['bytes']} for r in records]

project=Project(root);state,events,_=project.read(); task=state['tasks']['T000006']
receipt=json.loads((root/'AUDIT/phase2-delivery/acceptance-receipt.json').read_text())
checks=json.loads((root/'AUDIT/phase2-delivery/acceptance-hashes.json').read_text())
current_checks=[{'path':c['path'],'kind':c['kind'],'ok':(root/c['path']).is_file() and sha(root/c['path'])==c['expected']} for c in checks['checks']]
frozen=json.loads((root/'AUDIT/phase2-delivery/frozen-manifest.json').read_text())
runtime=json.loads((root/'AUDIT/phase2-runtime-validation-v3.json').read_text())
docs=json.loads((root/'AUDIT/phase2-docs-v3.json').read_text())
tested=json.loads((root/'AUDIT/phase2-architecture-s8-recovery-final-tests-v3.json').read_text())
baseline=json.loads((root/'AUDIT/phase2-baseline.json').read_text())
preserved={name:value for name,value in baseline['files'].items() if name.startswith(('AUDIT/','EXAMPLES/generated/','PROJECT_MEMORY/session_reports/')) or name in {'docs/adr/0001-local-ledger.md','PROJECT_MEMORY/notes/initial-understanding.md'}}
old_hash_checks=[{'path':p,'ok':(root/p).is_file() and sha(root/p)==h} for p,h in preserved.items()]
wheel=root/'dist/uados-1.1.0-py3-none-any.whl'
with zipfile.ZipFile(wheel) as archive:
    wheel_matches_current_source=all(archive.read(p.relative_to(root/'src').as_posix())==p.read_bytes() for p in (root/'src/uados').rglob('*') if p.is_file() and p.suffix in {'.py','.md','.mdc'} and '__pycache__' not in p.parts)
distribution=json.loads((root/'AUDIT/phase2-delivery/acceptance-distribution.json').read_text())
installed=Path(distribution['installed_import']).parent
installed_matches_current_source=all((installed/p.relative_to(root/'src/uados')).read_bytes()==p.read_bytes() for p in (root/'src/uados').rglob('*') if p.is_file() and p.suffix in {'.py','.md','.mdc'} and '__pycache__' not in p.parts)
audit=project.audit()
result={'receipt_files':records_valid(receipt['files']),'fresh260_checks':current_checks,
        'frozen81_checks':records_valid(frozen['files']),'runtime16_checks':records_valid(runtime['files']),
        'maintained_docs27_checks':[{'path':p,'ok':sha(root/p)==h} for p,h in docs['file_hashes'].items()],
        'source_same_as_independent75test_run':all(sha(root/p)==h for p,h in tested['source_after'].items()),
        'original184_files_checks':old_hash_checks,'original37_event_hashes_unchanged':[e['hash'] for e in events[:len(baseline['event_hashes'])]]==baseline['event_hashes'],
        'submitted_scope_unchanged':scope_snapshot(root,task['scope'])==task['submission_files'],
        'task_live_and_snapshot_evidence_problems':check_evidence(root,task['evidence']),
        'wheel_sha256':sha(wheel),'wheel_matches_receipt':sha(wheel)==distribution['wheel_sha256'],
        'wheel_matches_current_source':wheel_matches_current_source,'installed_matches_current_source':installed_matches_current_source,
        'current_audit':audit,'task_revision':task['revision'],'session_label':'Phase2-Architecture-Reviewer',
        'command':[sys.executable,'AUDIT/phase2-architecture-s8-D4-check.py'],'environment':{'python':sys.version,'platform':platform.platform()},
        'limits':['Four legacy original versions remain irrecoverable; this validates current revision, not complete historical preservation.','Hashes of nested manifests were explicitly recomputed; ordinary evidence registration does not supply transitive enforcement.','Full75suite already independently ran against same source; no claim of reexecuting it in this script.','Native products, hosted CI, authenticated identities and scientific external validity remain unvalidated.']}
booleans=['source_same_as_independent75test_run','original37_event_hashes_unchanged','submitted_scope_unchanged','wheel_matches_receipt','wheel_matches_current_source','installed_matches_current_source']
result['ok']=all(result[k] for k in booleans) and not result['task_live_and_snapshot_evidence_problems'] and audit['ok'] and not audit['history_ok'] and len(audit['historical_evidence_drift'])==4 and all(c['ok'] for k in ['receipt_files','fresh260_checks','frozen81_checks','runtime16_checks','maintained_docs27_checks','original184_files_checks'] for c in result[k])
print(json.dumps(result,indent=2,sort_keys=True))
sys.exit(0 if result['ok'] else 1)
