"""Independent proof that nested manifest validation remains contributor work."""
import hashlib,json,sys
from pathlib import Path
repo=Path(sys.argv[1]); script=repo/'AUDIT/phase2-architecture-probe-v2.py'
namespace={'__name__':'independent_fixture_helper','__file__':str(script)}
exec(compile(script.read_text().split('\nresults = {}\n')[0],str(script),'exec'),namespace)
f=namespace['Fixture'](scope='acceptance.txt')
try:
    source=f.root/'code.py'; manifest=f.root/'cr.txt'
    original_hash=hashlib.sha256(source.read_bytes()).hexdigest()
    manifest.write_text(json.dumps({'files':[{'path':'code.py','sha256':original_hash}]}))
    f.call('Author',namespace['gov'].replan_task,f.task,'Register changed fixture manifest explicitly before any consensus')
    f.call('Author',namespace['gov'].plan_task,f.task,'Verify recorded manifest','Check subordinate hashes manually',['plan.txt'])
    f.call('Author',namespace['gov'].propose_change,f.task,'Need acceptance verification','Sibling source hashes recorded',['Unscoped manual proof','Explicit manifest checks'],'Explicit manifest checks','Review scope','Human responsibility','Recheck subordinate inputs',['cr.txt'])
    f.role_plan=f.roles('Reviewer2')
    f.consensus()
    manifest_hash=hashlib.sha256(manifest.read_bytes()).hexdigest()
    source.write_text('Out-of-scope implementation changed after plan consensus\n')
    current_hash=hashlib.sha256(source.read_bytes()).hexdigest()
    claimed=f.call('Author',f.p.claim_task,f.task)
    result={'passed':current_hash!=original_hash and hashlib.sha256(manifest.read_bytes()).hexdigest()==manifest_hash and claimed['task']==f.task,
            'mechanism':'Declared acceptance scope and ordinary evidence protect manifest bytes; referenced sibling implementation hashes require explicit independent rechecking.',
            'independent_mechanical_fixture':True,'not_real_debate':True,
            'claim_succeeded_after_out_of_scope_change':True,'manifest_bytes_unchanged':True,'subordinate_source_hash_changed':True,
            'resolution_for_actual_T6':'No claim of automatic recursive manifest enforcement. Recheck all81 listed hashes and tested source equality at final result acceptance; reject any mismatch.'}
except Exception as error:
    result={'passed':False,'exception':type(error).__name__,'message':str(error)}
finally:
    f.close()
print(json.dumps(result,indent=2,sort_keys=True))
sys.exit(0 if result['passed'] else 1)
