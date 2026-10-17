"""Actual local clone/rebuild of four newest snapshot-aware scenario projects."""
import hashlib,json,shutil,subprocess,sys,tempfile
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root/'src'))
from uados.project import Project
from uados.storage import snapshot_problems
from uados.protocol import all_evidence
command_log=[]
def run(args,cwd):
    r=subprocess.run(args,cwd=str(cwd),capture_output=True,text=True)
    command_log.append({'command':args,'cwd':str(cwd),'exit_code':r.returncode})
    if r.returncode:raise RuntimeError(r.stderr)
    return r.stdout
with tempfile.TemporaryDirectory(prefix='uados-s8-current-scenarios-') as temporary:
    temporary=Path(temporary);snapshot=temporary/'snapshot';snapshot.mkdir()
    source=root/'EXAMPLES/phase2-snapshot-validation'
    shutil.copytree(source,snapshot/'scenarios')
    shutil.copy2(root/'.gitignore',snapshot/'.gitignore')
    run(['git','init','--initial-branch=main'],snapshot)
    run(['git','add','--all'],snapshot)
    run(['git','-c','user.name=Independent S8 review','-c','user.email=s8-review@localhost','commit','-m','Disposable snapshot-aware scenario clone'],snapshot)
    clone=temporary/'clone';run(['git','clone','--quiet',str(snapshot),str(clone)],temporary)
    audits={};rebuilds={};archives={}
    for relative in ('software','research','handover/day1','handover/day30'):
        path=clone/'scenarios'/relative
        assert not (path/'.uados/ledger.sqlite3').exists()
        rebuilds[relative]=Project.rebuild_ledger(path)
        project=Project(path);state,events,_=project.read()
        archived={(r['snapshot'],r['sha256']):r for e in events for r in all_evidence(e['state']) if 'snapshot' in r}
        problems=[problem for r in archived.values() for problem in snapshot_problems(path,r)]
        archives[relative]={'promised_snapshots_checked':len(archived),'problems':problems}
        audits[relative]=project.audit()
    result={'ok':all(v['ok'] and v['history_ok'] for v in audits.values()) and all(not v['problems'] and v['promised_snapshots_checked']>0 for v in archives.values()),'actual_local_git_clone':True,'freshest_snapshot_scenarios':'EXAMPLES/phase2-snapshot-validation','command_log':command_log,'rebuilds':rebuilds,'archives':archives,'audits':audits,'limitation':'Independent supplement: maintained verify_distribution.py lists older EXAMPLES/phase2-final projects in its eight audited roots. This specifically checks newer snapshot-aware projects without altering frozen source/receipt.'}
print(json.dumps(result,indent=2,sort_keys=True))
sys.exit(0 if result['ok'] else 1)
