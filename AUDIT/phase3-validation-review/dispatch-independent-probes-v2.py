import pathlib,json,tempfile,hashlib,sys,subprocess,os,time,copy
sys.path.insert(0,str(pathlib.Path.cwd()/"src"))
from uados.project import Project
from uados.dispatch import run_dispatch,verify_receipt,REQUEST_LIMIT
from uados.storage import UadosError,canonical,evidence_files
paths=["src/uados/dispatch.py","src/uados/cli.py","tests/test_dispatch.py","docs/dispatch.md"];before={p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() for p in paths};checks=[]
with tempfile.TemporaryDirectory(prefix="uados-dispatch-review-") as td:
 d=pathlib.Path(td).resolve();p=Project.initialize(d/"project","Dispatch review","Strict local receipts");root=p.root;req=root/"request.json";base={"format":"uados-dispatch-request","version":1,"provider":"fake","operation":"summarize","input":{"literal":"$() `script` \\u4e2d","binary_codepoints":[0,255]}}
 def write(v): req.write_bytes((canonical(v)+"\n").encode())
 write(base);initial={x:(root/x).read_bytes() for x in [".uados/ledger.sqlite3",".uados/events.jsonl",".uados/state.json"]}; a=run_dispatch(p,"request.json",d/"a.json");b=run_dispatch(p,"request.json",d/"b.json");assert a["response_sha256"]==b["response_sha256"] and verify_receipt(p,"request.json",d/"a.json")["verified"];checks.append({"name":"real_fake_deterministic_response_and_valid_receipt","ok":True}); good=(d/"a.json").read_bytes()
 def fail(name,action):
  try:action()
  except (UadosError,OSError) as e:checks.append({"name":name,"expected_failure":True,"diagnostic":str(e)});return
  raise AssertionError("Accepted "+name)
 for name,v in [("unknown_provider",dict(base,provider="Codex")),("bool_version",dict(base,version=True)),("unknown_field",dict(base,unknown=1)),("empty_operation",dict(base,operation="")),("nonstring_operation",dict(base,operation=[]))]:
  write(v);dest=d/(name+".json");fail(name,lambda:run_dispatch(p,"request.json",dest));assert not dest.exists()
 for name,raw in [("duplicate_json",b'{"format":"x","format":"uados-dispatch-request"}\n'),("nonfinite",b'{"a":NaN}\n'),("noncanonical",json.dumps(base,indent=2).encode()),("oversized",b'x'*(REQUEST_LIMIT+1)),("empty_request",b'')]:
  req.write_bytes(raw);dest=d/(name+".json");fail(name,lambda:run_dispatch(p,"request.json",dest));assert not dest.exists()
 write(base);fail("existing_output",lambda:run_dispatch(p,"request.json",d/"a.json"));assert (d/"a.json").read_bytes()==good;fail("internal_output",lambda:run_dispatch(p,"request.json",root/"inside.json"));fail("output_traversal",lambda:run_dispatch(p,"request.json",d/".."/"alias.json"));alias=d/"alias";alias.symlink_to(d/"a.json");fail("symlink_receipt",lambda:verify_receipt(p,"request.json",alias));checks.append({"name":"no_partial_or_staging_on_validation_failures","ok":not list(d.glob('.uados-dispatch-*'))})
 for name,change in [("provider_tamper",lambda x:x.update(provider="real")),("adapter_tamper",lambda x:x.update(adapter="forged")),("response_digest_tamper",lambda x:x.update(response_sha256="0"*64)),("bool_receipt_version",lambda x:x.update(version=True)),("response_tamper_rehash",lambda x:x["response"].update(accepted=False))]:
  x=json.loads(good);change(x)
  if name=="response_tamper_rehash":x["response_sha256"]=hashlib.sha256((canonical(x["response"])+"\n").encode()).hexdigest()
  target=d/(name+".json");target.write_bytes((canonical(x)+"\n").encode());fail(name,lambda:verify_receipt(p,"request.json",target))
 # Current implementation treats timestamps as caller-supplied bounded assertions.
 x=json.loads(good);x['started_at']='not-a-time';x['ended_at']='earlier';timestamp=d/'timestamp-claim.json';timestamp.write_bytes((canonical(x)+'\n').encode()); timestamp_accepted=verify_receipt(p,'request.json',timestamp)['verified'];checks.append({'name':'timestamp_assertion_not_authenticated_or_dateparsed','accepted':timestamp_accepted,'limitation':'bounded nonempty strings only; request/response verification is independent of observed time authenticity'})
 req.write_bytes((canonical(dict(base,input={"changed":True}))+"\n").encode());fail("request_drift",lambda:verify_receipt(p,"request.json",d/"a.json"));write(base)
 # Registration does not automatically import external files; explicit copy establishes normal evidence.
 (root/'receipt-proof.json').write_bytes(good);record=evidence_files(root,['receipt-proof.json'])[0];assert (root/record['snapshot']).read_bytes()==good;checks.append({'name':'copied_receipt_ordinary_evidence_snapshot','ok':True})
 env=dict(os.environ,PYTHONPATH=str(pathlib.Path.cwd()/"src"));write(dict(base,provider='real'));cmd=[sys.executable,'-m','uados','--project',str(root),'dispatch','run','--request','request.json','--output',str(d/'cli-unknown.json')];r=subprocess.run(cmd,env=env,capture_output=True,text=True);assert r.returncode==2 and not (d/'cli-unknown.json').exists();checks.append({'name':'cli_unknown_provider_exit2_no_output','ok':True,'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
 assert all((root/x).read_bytes()==v for x,v in initial.items());checks.append({'name':'all_dispatch_success_failure_no_database_events_state_mutation','ok':True}); assert not list(d.glob('.uados-dispatch-*'))
after={p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() for p in paths};assert before==after
out={'reviewer':'Phase3-Validation-Reviewer','session':'S000012','checks':checks,'count':len(checks),'source_before':before,'source_after':after,'unchanged':True,'temporary_projects_removed':True,'limits':['Fake adapter only; no provider invocation/signature/identity/network/retries.','Timestamps are unauthenticated bounded strings; no observed time validity guarantee.']}
with pathlib.Path('AUDIT/phase3-validation-review/dispatch-independent-probes-v1.json').open('x') as f:json.dump(out,f,indent=2)
print(json.dumps({'checks':len(checks),'unchanged':True,'timestamp_strings_accepted':timestamp_accepted},indent=2))
