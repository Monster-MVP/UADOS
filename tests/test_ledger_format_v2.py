"""Ledger format 2.1: digest-only events, harvest snapshots, report pruning, compact."""

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from uados.project import Project, Project as _P
from uados.resilience import BackoffConfig, RateLimitError, classify_error, retry_with_backoff
from uados.storage import (UadosError, canonical, commit_event, connect, create_schema,
                           digest, event_header, load_ledger, streaming_load_ledger)


class LedgerFormatV2Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "proj"
        self.project = Project.initialize(self.root, "fmt-v2", "ledger format v2 coverage")

    def _events_from_db(self):
        with connect(self.root) as connection:
            rows = connection.execute("SELECT value FROM events ORDER BY sequence").fetchall()
        return [json.loads(raw) for (raw,) in rows]

    def test_metadata_events_are_digest_only_and_evidence_events_snapshot(self):
        session = self.project.start_session("agent")
        self.project.acknowledge(session["session"], session["report_hash"])
        # note.add touches only notes: no harvestable evidence change
        self.project.add_note(session["session"], "Note", "metadata only")
        events = self._events_from_db()
        note_event = events[-1]
        self.assertIn("state_digest", note_event)
        self.assertNotIn("state", note_event)
        # the first event always carries a full state snapshot
        self.assertIn("state", events[0])
        # a decision adds evidence records: the event must embed a snapshot
        evidence = self.root / "evidence"
        evidence.mkdir(exist_ok=True)
        (evidence / "decision.md").write_text("decision evidence", encoding="utf-8")
        self.project.add_decision(session["session"], "ADR", "problem", ["a", "b"], "decision",
                                  "reason", ["evidence/decision.md"], "risk")
        events = self._events_from_db()
        self.assertIn("state", events[-1])
        self.assertIn("state_digest", events[-1])
        # every event carries a digest and the full ledger verifies
        for event in events:
            self.assertIn("state_digest", event)
        self.assertTrue(self.project.audit()["ok"])

    def test_mixed_legacy_and_digest_events_chain_verifies(self):
        # Simulate a legacy head event (full state, no state_digest) followed by
        # a 2.1 digest-only event; the loader must accept the mixed chain.
        with connect(self.root) as connection:
            state, events = streaming_load_ledger(connection, keep_events=False)
            legacy_state = json.loads(canonical(state))
            legacy_state["phase"] = "execution"
            legacy = dict(event_header(events, "legacy.kind", "legacy-agent", "legacy full-state event"), state=legacy_state)
            legacy["hash"] = digest(legacy)
            connection.execute("INSERT INTO events(sequence,value) VALUES (?,?)", (legacy["sequence"], canonical(legacy)))
            connection.execute("INSERT OR REPLACE INTO state(id,value) VALUES (1,?)", (canonical(legacy_state),))
            connection.commit()
            fresh_state, fresh_events = streaming_load_ledger(connection, keep_events=False)
            self.assertEqual(len(fresh_events), len(events) + 1)
            self.assertEqual(fresh_state["phase"], "execution")

    def test_session_reports_stop_accumulating_content(self):
        session = self.project.start_session("agent")
        self.project.acknowledge(session["session"], session["report_hash"])
        first = self.project.read()[0]["sessions"][session["session"]]
        self.assertIn("report", first)
        for report in first["reports"]:
            self.assertNotIn("content", report)
        refreshed = self.project.refresh_session(session["session"])
        self.project.acknowledge(session["session"], refreshed["report_hash"])
        state = self.project.read()[0]
        stored = state["sessions"][session["session"]]
        for report in stored["reports"]:
            self.assertNotIn("content", report)
        # report files exist on disk and the projection stays drift-free
        for report in stored["reports"]:
            self.assertTrue((self.root / report["path"]).is_file())
        self.assertEqual(self.project.read()[2], [])
        closed = self.project.close_session(session["session"], "done", ["next action"])
        self.assertTrue(closed["closed"])
        stored = self.project.read()[0]["sessions"][session["session"]]
        self.assertNotIn("report", stored)
        for report in stored["reports"]:
            self.assertNotIn("content", report)

    def test_compact_rewrites_verifies_and_keeps_working(self):
        session = self.project.start_session("agent")
        self.project.acknowledge(session["session"], session["report_hash"])
        for index in range(5):
            self.project.add_note(session["session"], "Note %d" % index, "body %d" % index)
        before_events = len(self._events_from_db())
        result = Project.compact(self.root)
        self.assertEqual(result["previous_events"], before_events)
        self.assertEqual(result["new_events"], before_events + 1)
        compacted = self._events_from_db()
        self.assertEqual(len(compacted), before_events + 1)
        self.assertEqual(compacted[-1]["kind"], "ledger.compact")
        self.assertIn("state", compacted[-1])
        self.assertTrue((self.root / ".uados" / result["backup_ledger"]).is_file())
        self.assertTrue((self.root / ".uados" / result["backup_journal"]).is_file())
        # pruned closed/open state and audit stays green with zero drift
        audit = self.project.audit()
        self.assertTrue(audit["ok"])
        self.assertEqual(audit["projection_drift"], [])
        # the journal on disk matches the compacted rows and stays small
        journal_lines = (self.root / ".uados" / "events.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(journal_lines), before_events + 1)
        # subsequent mutations keep working on the compacted ledger; the compact
        # event changed the context, so the session refreshes and re-acknowledges
        refreshed = self.project.refresh_session(session["session"])
        self.project.acknowledge(session["session"], refreshed["report_hash"])
        self.project.add_note(session["session"], "After compact", "still working")
        self.assertTrue(self.project.audit()["ok"])
        # a second compaction over digest-only sources keeps the same shape
        before_second = len(self._events_from_db())
        second = Project.compact(self.root)
        self.assertEqual(second["new_events"], before_second + 1)
        self.assertTrue(self.project.audit()["ok"])

    def test_rebuild_from_compacted_export(self):
        session = self.project.start_session("agent")
        self.project.acknowledge(session["session"], session["report_hash"])
        self.project.add_note(session["session"], "Note", "body")
        Project.compact(self.root)
        (self.root / ".uados" / "ledger.sqlite3").unlink()
        result = Project.rebuild_ledger(self.root)
        self.assertTrue(result["rebuilt"])
        self.assertTrue(self.project.audit()["ok"])
        successor = self.project.start_session("Successor")
        self.assertTrue(successor["report"]["failed_approaches"] is not None)

    def test_backoff_interrupts_propagate_unwrapped(self):
        def interrupted():
            raise KeyboardInterrupt("operator stop")
        with self.assertRaises(KeyboardInterrupt):
            retry_with_backoff(interrupted, config=BackoffConfig(max_attempts=3))
        def exiting():
            raise SystemExit(2)
        with self.assertRaises(SystemExit):
            retry_with_backoff(exiting, config=BackoffConfig(max_attempts=3))

    def test_typed_rate_limit_error_parses_retry_after(self):
        retryable, delay, category = classify_error(RateLimitError("HTTP 429; Retry-After: 17"))
        self.assertTrue(retryable)
        self.assertEqual(delay, 17.0)
        self.assertEqual(category, "rate_limit")


if __name__ == "__main__":
    unittest.main()
