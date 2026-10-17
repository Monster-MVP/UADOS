"""Separately authored review probes, outside maintained implementation/tests."""
import json, tempfile, pathlib, sys, subprocess, os, shutil, hashlib, time, sqlite3
from unittest import mock
sys.path.insert(0,str(pathlib.Path.cwd()/"src"))
from uados import trust
from uados.project import Project,write_projections
from uados.storage import UadosError,canonical,digest
paths=["src/uados/trust.py","src/uados/cli.py","tests/test_trust.py","docs/trust.md"]
before={p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() for p in paths}
checks=[]
def expect_failure(name,call):
    try:call()
    except (UadosError,OSError) as exc:checks.append({"name":name,"expected_failure":True,"exception_type":type(exc).__name__,"diagnostic":str(exc)}); return
    raise AssertionError("Accepted "+name)
with tempfile.TemporaryDirectory(prefix="uados-independent-review-") as tmp:
 d=pathlib.Path(tmp).resolve(); key=d/"key"; subprocess.run(["ssh-keygen","-q","-t","ed25519","-N","","-f",str(key)],check=True,capture_output=True)
 allowed=d/"allowed"; allowed.write_text('reviewer namespaces="'+trust.NAMESPACE+'" '+(d/"key.pub").read_text())
 p=Project.initialize(d/"project","Review","Independent legacy integrity",protocol_version=1); bundle=d/"bundle"
 snapshots={name:(p.root/name).read_bytes() for name in [".uados/events.jsonl",".uados/state.json",".uados/ledger.sqlite3"]}
 start=time.monotonic(); signed=trust.create_checkpoint(p,bundle,"reviewer",key); verified=trust.verify_checkpoint(p,bundle,"reviewer",signed["checkpoint_sha256"],allowed,require_current=True)
 assert verified["ok"] and verified["signature_verified"] and verified["covers_current_head"]
 assert all((p.root/name).read_bytes()==raw for name,raw in snapshots.items()); checks.append({"name":"real_legacy1_checkpoint_no_event_or_database_change","ok":True,"seconds":time.monotonic()-start})
 marker=(bundle/"COMPLETE").read_bytes(); (bundle/"COMPLETE").unlink(); expect_failure("missing_complete_marker",lambda:trust.verify_checkpoint(p,bundle,"reviewer",signed["checkpoint_sha256"],allowed)); (bundle/"COMPLETE").write_bytes(marker)
 expect_failure("same_target_recreate_immutable",lambda:trust.create_checkpoint(p,bundle,"reviewer",key)); assert (bundle/"COMPLETE").read_bytes()==marker
 (bundle/"COMPLETE").write_text(canonical({"checkpoint_sha256":"0"*64,"signature_sha256":"0"*64})+"\n"); expect_failure("forged_complete_marker",lambda:trust.verify_checkpoint(p,bundle,"reviewer",signed["checkpoint_sha256"],allowed)); (bundle/"COMPLETE").write_bytes(marker)
 expect_failure("expected_pin_mismatch",lambda:trust.verify_checkpoint(p,bundle,"reviewer","0"*64,allowed))
 revoked=d/"revoked"; revoked.write_bytes((d/"key.pub").read_bytes()); expect_failure("actual_revoked_ed25519_signature",lambda:trust.verify_checkpoint(p,bundle,"reviewer",signed["checkpoint_sha256"],allowed,revocations=revoked))
 p.start_session("Later"); historical=trust.verify_checkpoint(p,bundle,"reviewer",signed["checkpoint_sha256"],allowed); assert historical["ok"] and not historical["covers_current_head"]
 expect_failure("historical_prefix_require_current",lambda:trust.verify_checkpoint(p,bundle,"reviewer",signed["checkpoint_sha256"],allowed,require_current=True)); checks.append({"name":"historical_prefix_explicit","ok":True,"current_sequence":historical["current_sequence"],"checkpoint_sequence":historical["sequence"]})
 (p.root/"PROJECT_STATE.md").write_text("Current projection drift"); drift=trust.verify_checkpoint(p,bundle,"reviewer",signed["checkpoint_sha256"],allowed); assert not drift["ok"] and drift["signature_verified"] and drift["signed_audit_assertion"]["current_ok"] and not drift["current_audit"]["ok"]; checks.append({"name":"separate_valid_signed_past_assertion_from_current_audit_failure","ok":True}); p.audit(repair=True)
 environment=dict(os.environ,PYTHONPATH=str(pathlib.Path.cwd()/"src")); cmd=[sys.executable,"-m","uados","--project",str(p.root),"trust","verify","--bundle",str(bundle),"--principal","reviewer","--expected-sha256",signed["checkpoint_sha256"],"--allowed-signers",str(allowed)]
 (p.root/"PROJECT_STATE.md").write_text("Current projection drift"); r=subprocess.run(cmd,env=environment,capture_output=True,text=True); assert r.returncode==1 and json.loads(r.stdout)["signature_verified"] and not json.loads(r.stdout)["ok"]; checks.append({"name":"cli_current_audit_failure_exit1","ok":True,"returncode":r.returncode}); p.audit(repair=True)
 target=d/"concurrent"; cmd=[sys.executable,"-m","uados","--project",str(p.root),"trust","checkpoint","--output",str(target),"--principal","reviewer","--key",str(key)]; processes=[subprocess.Popen(cmd,env=environment,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(4)]; results=[]
 for proc in processes:
  stdout,stderr=proc.communicate(timeout=30); results.append({"returncode":proc.returncode,"stdout":stdout,"stderr":stderr})
 assert sorted(r["returncode"] for r in results)==[0,2,2,2],results; winner=json.loads(next(r["stdout"] for r in results if r["returncode"]==0)); assert trust.verify_checkpoint(p,target,"reviewer",winner["checkpoint_sha256"],allowed,require_current=True)["ok"]; checks.append({"name":"four_real_processes_same_target_one_winner","ok":True,"returncodes":[r["returncode"] for r in results],"files":sorted(x.name for x in target.iterdir()),"event_count":p.audit()["event_count"]})
 incomplete=d/"partial"; real_link=trust.os.link; calls=[0]
 def broken(src,dst):
  calls[0]+=1
  if calls[0]==2:raise OSError("Independent injected disk publication failure")
  return real_link(src,dst)
 with mock.patch("uados.trust.os.link",side_effect=broken):expect_failure("disk_failure_after_exclusive_directory_creation",lambda:trust.create_checkpoint(p,incomplete,"reviewer",key))
 assert incomplete.is_dir() and (incomplete/"checkpoint.json").exists() and not (incomplete/"COMPLETE").exists(); expect_failure("incomplete_disk_publication_rejected",lambda:trust.verify_checkpoint(p,incomplete,"reviewer",winner["checkpoint_sha256"],allowed)); assert not list(d.glob(".uados-checkpoint-*")); checks.append({"name":"partial_output_inspectable_and_staging_cleaned","ok":True,"files":sorted(x.name for x in incomplete.iterdir())})
 shimdir=d/"shim"; shimdir.mkdir(); shim=shimdir/"ssh-keygen"; shim.write_text("#!"+sys.executable+"\nimport time\ntime.sleep(5)\n"); shim.chmod(0o700)
 with mock.patch.dict(os.environ,{"PATH":str(shimdir)}),mock.patch("uados.trust.TIMEOUT",0.2):
  started=time.monotonic(); expect_failure("real_process_timeout",lambda:trust.create_checkpoint(p,d/"timed-out","reviewer",key)); elapsed=time.monotonic()-started; assert elapsed<2; assert not (d/"timed-out").exists(); checks.append({"name":"timeout_real_process_bound","ok":True,"seconds":elapsed,"operation_timeout_seconds":0.2})
 forged=Project.initialize(d/"forged-project","Forge review","Observe anchor",protocol_version=2); forged.start_session("Original"); forged_bundle=d/"forged-bundle"; checkpoint=trust.create_checkpoint(forged,forged_bundle,"reviewer",key); state,events,_=forged.read(); state["objective"]="Adversary recomputed local history"; events[-1]["state"]=state; events[-1]["hash"]=digest({k:v for k,v in events[-1].items() if k!="hash"})
 with sqlite3.connect(str(forged.root/".uados/ledger.sqlite3")) as conn:
  conn.execute("UPDATE state SET value=? WHERE id=1",(canonical(state),)); conn.execute("UPDATE events SET value=? WHERE sequence=?",(canonical(events[-1]),len(events)))
 write_projections(forged.root,state,events); assert forged.audit()["ok"]; expect_failure("self_rehashed_locally_valid_ledger_rejected_by_real_anchor",lambda:trust.verify_checkpoint(forged,forged_bundle,"reviewer",checkpoint["checkpoint_sha256"],allowed))
 temporary_root=str(d)
assert not pathlib.Path(temporary_root).exists()
after={p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() for p in paths}
record={"reviewer":"Phase3-Validation-Reviewer","session":"S000012","checks":checks,"count":len(checks),"source_before":before,"source_after":after,"source_unchanged":before==after,"ephemeral_external_keys_deleted":True,"limits":["Local macOS/OpenSSH only; publication disk error injected explicitly.","Timeout probe executes a real sleeping replacement executable with reduced 0.2 second test bound; it does not claim an actual OpenSSH cryptographic timeout.","No maintained implementation/tests edited; all projects and keys disposable."]}
with pathlib.Path("AUDIT/phase3-validation-review/independent-probes-v3.json").open("x") as f:json.dump(record,f,indent=2)
print(json.dumps({"checks":len(checks),"source_unchanged":before==after,"ephemeral_keys_deleted":True},indent=2))
