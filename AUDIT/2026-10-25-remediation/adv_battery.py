"""Adversarial verification battery for UADOS 2.1.0 (run from /tmp, repo read-only)."""
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path("/Volumes/wdmonster/emonsterhome/Desktop/上海交通大学/agent-work")
sys.path.insert(0, str(REPO / "src"))

from uados.project import Project
from uados.storage import (UadosError, canonical, connect, digest, event_header,
                           commit_event, streaming_load_ledger, load_ledger, iter_event_states,
                           atomic_write_lines, iter_journal_lines)

RESULTS = []

def check(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (" | " + detail if detail else ""))

def expect_error(fn, needle=None):
    try:
        fn()
        return False, "no error raised"
    except UadosError as exc:
        if needle and needle not in str(exc):
            return False, "wrong error: " + str(exc)[:120]
        return True, str(exc)[:120]

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp) / "adv"
    p = Project.initialize(root, "adv", "adversarial battery")

    # ---- a) mixed chain + tamper variants ----
    s = p.start_session("agent")
    p.acknowledge(s["session"], s["report_hash"])
    ev = root / "evidence"; ev.mkdir()
    (ev / "d.md").write_text("decision evidence", encoding="utf-8")
    p.add_decision(s["session"], "ADR", "prob", ["a", "b"], "dec", "why", ["evidence/d.md"], "risk")
    p.add_note(s["session"], "n1", "note body")

    def rows():
        with connect(root) as c:
            return c.execute("SELECT sequence,value FROM events ORDER BY sequence").fetchall()

    # baseline: both modes agree
    with connect(root) as c:
        st1, ev1 = streaming_load_ledger(c, keep_events=False)
        st2, ev2 = load_ledger(c, keep_events=True)
    check("a0 baseline both modes load", canonical(st1) == canonical(st2) and len(ev1) == len(ev2))

    # tamper digest-only summary (last note event)
    rs = rows()
    seq, raw = rs[-1]
    obj = json.loads(raw); obj["summary"] = "tampered"
    with connect(root) as c:
        c.execute("UPDATE events SET value=? WHERE sequence=?", (canonical(obj), seq)); c.commit()
    with connect(root) as c:
        ok, d = expect_error(lambda: streaming_load_ledger(c), "inconsistent")
    check("a1 tampered digest-only summary rejected", ok, d)
    with connect(root) as c:
        c.execute("UPDATE events SET value=? WHERE sequence=?", (raw, seq)); c.commit()

    # tamper state_digest of the digest-only event
    obj = json.loads(raw); obj["state_digest"] = "0" * 64
    obj2 = dict(obj); obj2.pop("hash")
    obj["hash"] = digest(obj2)
    with connect(root) as c:
        c.execute("UPDATE events SET value=? WHERE sequence=?", (canonical(obj), seq)); c.commit()
        ok, d = expect_error(lambda: streaming_load_ledger(c), "disagrees")
    check("a2 forged state_digest (rehashed) rejected by state-row anchor", ok, d)
    with connect(root) as c:
        c.execute("UPDATE events SET value=? WHERE sequence=?", (raw, seq)); c.commit()

    # summary containing literal ,\"state\": escaped payload cannot spoof extraction
    obj = json.loads(raw)
    try:
        obj["summary"] = 'x","state":{},"summary":"injected'
    except Exception:
        obj["summary"] = 'plain'
    obj2 = dict(obj); obj2.pop("hash"); obj["hash"] = digest(obj2)
    with connect(root) as c:
        c.execute("UPDATE events SET value=? WHERE sequence=?", (canonical(obj), seq)); c.commit()
        st_a, ev_a = streaming_load_ledger(c, keep_events=False)
        st_b, ev_b = load_ledger(c, keep_events=True)
    agree = canonical(st_a) == canonical(st_b) and ev_a[-1]["hash"] == ev_b[-1]["hash"]
    check("a3 escaped-injection summary keeps both modes consistent", agree)
    with connect(root) as c:
        c.execute("UPDATE events SET value=? WHERE sequence=?", (raw, seq)); c.commit()

    # non-canonical whitespace row: verification anchors parsed CONTENT, so a
    # whitespace-only variance is content-neutral and accepted (same as 2.0.0);
    # any content change is caught by a1/a2. Record the design fact.
    with connect(root) as c:
        c.execute("UPDATE events SET value=? WHERE sequence=?", (raw.replace('","', '", "', 1), seq)); c.commit()
        try:
            streaming_load_ledger(c); accepted = True
        except UadosError:
            accepted = False
    check("a4 whitespace-only variance is content-neutral (by design)", accepted)
    with connect(root) as c:
        c.execute("UPDATE events SET value=? WHERE sequence=?", (raw, seq)); c.commit()

    # ---- b) state anchoring ----
    with connect(root) as c:
        state, _ = streaming_load_ledger(c, keep_events=False)
        forged = json.loads(canonical(state)); forged["phase"] = "execution"
        c.execute("UPDATE state SET value=? WHERE id=1", (canonical(forged),)); c.commit()
        ok, d = expect_error(lambda: streaming_load_ledger(c), "disagrees")
    check("b1 state-row-only tamper rejected", ok, d)
    with connect(root) as c:
        c.execute("UPDATE state SET value=? WHERE id=1", (canonical(state),)); c.commit()

    # last event stripped of both state and state_digest -> rejected
    obj = json.loads(raw); obj.pop("state_digest", None); obj.pop("state", None)
    obj2 = dict(obj); obj2.pop("hash"); obj["hash"] = digest(obj2)
    with connect(root) as c:
        c.execute("UPDATE events SET value=? WHERE sequence=?", (canonical(obj), seq)); c.commit()
        ok, d = expect_error(lambda: streaming_load_ledger(c), "disagrees")
    check("b2 tail without state anchor rejected", ok, d)
    with connect(root) as c:
        c.execute("UPDATE events SET value=? WHERE sequence=?", (raw, seq)); c.commit()

    # ---- c) harvest coverage: transient evidence must appear in snapshots ----
    s2 = p.start_session("agent2")
    p.acknowledge(s2["session"], s2["report_hash"])
    (ev / "t1.md").write_text("task evidence v1", encoding="utf-8")
    t = p.add_task(s2["session"], "T", "desc", "routine", ["src/x.py"])
    (root / "src").mkdir(exist_ok=True); (root / "src/x.py").write_text("x = 1", encoding="utf-8")
    (ev / "plan.md").write_text("plan evidence", encoding="utf-8")
    from uados import governance as gov
    gov.plan_task(p, s2["session"], t["task"], "steps", "checks", ["evidence/plan.md"])
    p.claim_task(s2["session"], t["task"])
    p.record_task(s2["session"], t["task"], "v1", ["evidence/t1.md"])
    p.add_note(s2["session"], "meta", "between evidence states")  # digest-only gap
    (ev / "t2.md").write_text("task evidence v2", encoding="utf-8")
    p.record_task(s2["session"], t["task"], "v2", ["evidence/t2.md"])
    with connect(root) as c:
        snaps = [(sq, st) for sq, st in iter_event_states(c)]
    def snapshot_has_path(path):
        for _, st in snaps:
            for task in st.get("tasks", {}).values():
                for record in task.get("evidence", []):
                    if record.get("path") == path:
                        return True
            for adr in st.get("decisions", []):
                for record in adr.get("evidence", []):
                    if record.get("path") == path:
                        return True
        return False
    check("c1 transient evidence record present in harvest snapshots", snapshot_has_path("evidence/t1.md"), "snapshots=%d" % len(snaps))
    check("c1b current evidence present", snapshot_has_path("evidence/t2.md"))
    aud = p.audit()
    check("c2 audit ok with history intact", aud["ok"], "records=%d" % aud["evidence_records_checked"])

    # ---- d) compact attacks on this real lifecycle ledger ----
    res = Project.compact(root)
    with connect(root) as c:
        st_c, ev_c = streaming_load_ledger(c, keep_events=False)
    check("d1 compact verifies", len(ev_c) == res["new_events"])
    # tamper a digest-only summary post-compact
    with connect(root) as c:
        rs2 = c.execute("SELECT sequence,value FROM events ORDER BY sequence").fetchall()
        sq2, raw2 = rs2[2]
        o = json.loads(raw2); o["summary"] = "evil"
        c.execute("UPDATE events SET value=? WHERE sequence=?", (canonical(o), sq2)); c.commit()
        ok, d = expect_error(lambda: streaming_load_ledger(c), "inconsistent")
    check("d2 post-compact digest-only tamper rejected", ok, d)
    with connect(root) as c:
        c.execute("UPDATE events SET value=? WHERE sequence=?", (raw2, sq2)); c.commit()
        # delete a middle event
        keep = rs2[5][0]
        c.execute("DELETE FROM events WHERE sequence=?", (keep,)); c.commit()
        ok, d = expect_error(lambda: streaming_load_ledger(c), "broken")
    check("d3 deleted middle event rejected", ok, d)
    with connect(root) as c:
        c.execute("INSERT INTO events(sequence,value) VALUES (?,?)", rs2[5])
        c.commit()
    # rebuild from journal + state.json
    before_state = json.loads((root / ".uados/state.json").read_text())
    (root / ".uados/ledger.sqlite3").unlink()
    r = Project.rebuild_ledger(root)
    after_state = json.loads((root / ".uados/state.json").read_text())
    check("d4 rebuild from compacted export equals state", canonical(before_state) == canonical(after_state), "events=%s" % r["event_count"])
    check("d5 audit after rebuild", p.audit()["ok"])
    # compact twice + mutations
    Project.compact(root)
    r3 = p.refresh_session(s2["session"])
    p.acknowledge(s2["session"], r3["report_hash"])
    p.add_note(s2["session"], "post2", "after second compact")
    check("d6 second compact + mutations green", p.audit()["ok"])

    # ---- e) pruning flow ----
    p.close_session(s["session"], "battery close", ["next"])
    st = p.read()[0]
    closed = st["sessions"][s["session"]]
    check("e1 closed session has no report content", "report" not in closed and all("content" not in x for x in closed["reports"]))
    active = st["sessions"][s2["session"]]
    check("e2 active session keeps only current report", "report" in active and all("content" not in x for x in active["reports"]))
    files_ok = all((root / x["path"]).is_file() for sess in st["sessions"].values() for x in sess["reports"])
    check("e3 all report files exist on disk", files_ok)
    check("e4 zero projection drift", p.read()[2] == [])

    # ---- f) journal drift variants ----
    journal = root / ".uados/events.jsonl"
    original = journal.read_bytes()
    with connect(root) as c:
        lines = [l.encode("utf-8") for l in iter_journal_lines(c)]
    def drift_check(mutate_bytes, label):
        journal.write_bytes(mutate_bytes)
        with connect(root) as c:
            from uados.project import journal_drift
            return journal_drift(root, c) == [".uados/events.jsonl"]
    text = original.decode()
    check("f1 extra line detected", drift_check(original + lines[0], "extra"))
    check("f2 missing last line detected", drift_check(b"".join(lines[:-1]), "missing"))
    body = list(lines); body[2] = body[2].replace(b'"kind":', b'"kind": ', 1) if b'"kind":' in body[2] else (b"X" + body[2])
    check("f3 byte change detected", drift_check(b"".join(body), "change"))
    check("f4 missing trailing newline detected", drift_check(original.rstrip(b"\n"), "nonl"))
    journal.write_bytes(original)
    check("f5 restored journal drift-free", p.read()[2] == [])

    # ---- g) resilience ----
    from uados.resilience import BackoffConfig, retry_with_backoff, classify_error, RateLimitError
    def boom(): raise KeyboardInterrupt
    try:
        retry_with_backoff(boom, config=BackoffConfig(max_attempts=3)); check("g1 KeyboardInterrupt propagates", False)
    except KeyboardInterrupt: check("g1 KeyboardInterrupt propagates", True)
    r, delay, cat = classify_error(RateLimitError("HTTP 429; Retry-After: 12.5"))
    check("g2 typed rate limit parses Retry-After", r and delay == 12.5 and cat == "rate_limit", str(delay))
    r, delay, cat = classify_error(RuntimeError("HTTP 429 too many requests; retry-after: 30 seconds"))
    check("g3 keyword-gated retry-after parsing", r and delay == 30.0 and cat == "rate_limit_429", str((r, delay, cat)))
    r2, delay2, cat2 = classify_error(RuntimeError("server busy, retry-after: 30"))
    check("g3b no-keyword message stays permanent (by design)", (not r2) and cat2 == "permanent")

print()
fails = [x for x in RESULTS if not x[1]]
print("TOTAL %d / PASS %d / FAIL %d" % (len(RESULTS), len(RESULTS) - len(fails), len(fails)))
for name, _, detail in fails:
    print("FAILED:", name, "|", detail)
sys.exit(1 if fails else 0)
