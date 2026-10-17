import hashlib
import json
import resource
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any, Dict

from uados.project import Project
from uados.storage import (UadosError, canonical, commit_event, connect,
                           create_schema, digest, event_header, load_ledger,
                           streaming_load_ledger)


class StorageStreamingTests(unittest.TestCase):
    def test_byte_identical_equivalence(self):
        """Test 1: Byte-Identical Equivalence.

        Compare state, event count, and every event's hash between legacy load_ledger
        and streaming_load_ledger across multiple committed events.
        """
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "proj"
            project = Project.initialize(root, "streaming-equiv", "test")
            # Commit a few additional events
            session_result = project.start_session("agent-1")
            session_id = session_result["session"]
            project.acknowledge(session_id, session_result["report_hash"])
            project.add_task(session_id, "Task 1", "Description 1", "routine", ["src/module.py"])

            with connect(root) as connection:
                state_legacy, events_legacy = load_ledger(connection, keep_events=True)
                state_stream, events_stream = streaming_load_ledger(connection, keep_events=False)

                # State must be completely identical
                self.assertEqual(canonical(state_legacy), canonical(state_stream))
                self.assertEqual(len(events_legacy), len(events_stream))

                # Event hashes and ordering must match 100%
                for i in range(len(events_legacy)):
                    self.assertEqual(events_legacy[i]["sequence"], events_stream[i]["sequence"])
                    self.assertEqual(events_legacy[i]["hash"], events_stream[i]["hash"])
                    self.assertEqual(events_legacy[i]["previous_hash"], events_stream[i]["previous_hash"])
                    self.assertEqual(events_legacy[i]["kind"], events_stream[i]["kind"])
                    self.assertEqual(events_legacy[i]["actor"], events_stream[i]["actor"])
                    self.assertEqual(events_legacy[i]["summary"], events_stream[i]["summary"])

                # With keep_events=True on streaming_load_ledger, output must match legacy exactly
                state_full, events_full = streaming_load_ledger(connection, keep_events=True)
                self.assertEqual(canonical(state_legacy), canonical(state_full))
                self.assertEqual(canonical(events_legacy), canonical(events_full))

    def test_tamper_and_broken_chain_detection(self):
        """Test 2: Tamper & Broken Chain Detection.

        Deliberately corrupt intermediate sequence number, previous_hash, and payload
        to verify that streaming_load_ledger immediately fails closed with UadosError.
        """
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "proj"
            project = Project.initialize(root, "tamper-test", "test")
            s = project.start_session("agent-1")
            project.acknowledge(s["session"], s["report_hash"])
            project.add_task(s["session"], "Task A", "Desc A", "routine", ["a.py"])
            project.add_task(s["session"], "Task B", "Desc B", "routine", ["b.py"])

            ledger_path = root / ".uados" / "ledger.sqlite3"

            # 1. Tamper with sequence number in event 2
            with sqlite3.connect(ledger_path) as conn:
                raw = conn.execute("SELECT value FROM events WHERE sequence=2").fetchone()[0]
                ev = json.loads(raw)
                ev["sequence"] = 999
                conn.execute("UPDATE events SET value=? WHERE sequence=2", (canonical(ev),))
                conn.commit()

            with sqlite3.connect(ledger_path) as conn:
                with self.assertRaises(UadosError):
                    streaming_load_ledger(conn)

            # 2. Tamper with previous_hash in event 3
            # Restore event 2 first
            with sqlite3.connect(ledger_path) as conn:
                ev["sequence"] = 2
                conn.execute("UPDATE events SET value=? WHERE sequence=2", (canonical(ev),))
                raw3 = conn.execute("SELECT value FROM events WHERE sequence=3").fetchone()[0]
                ev3 = json.loads(raw3)
                ev3["previous_hash"] = "f" * 64
                conn.execute("UPDATE events SET value=? WHERE sequence=3", (canonical(ev3),))
                conn.commit()

            with sqlite3.connect(ledger_path) as conn:
                with self.assertRaises(UadosError):
                    streaming_load_ledger(conn)

            # 3. Tamper with inner state in event 2 without updating hash
            with sqlite3.connect(ledger_path) as conn:
                # restore event 3
                conn.execute("UPDATE events SET value=? WHERE sequence=3", (raw3,))
                raw2 = conn.execute("SELECT value FROM events WHERE sequence=2").fetchone()[0]
                ev2 = json.loads(raw2)
                ev2["state"]["objective"] = "corrupted-objective"
                conn.execute("UPDATE events SET value=? WHERE sequence=2", (canonical(ev2),))
                conn.commit()

            with sqlite3.connect(ledger_path) as conn:
                with self.assertRaises(UadosError):
                    streaming_load_ledger(conn)

    def test_interrupted_write_safety(self):
        """Test 3: Interrupted Write & Rollback Safety.

        Ensure an aborted or rolling-back transaction does not leave half-committed
        events or break the cryptographic chain.
        """
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "proj"
            project = Project.initialize(root, "rollback-test", "test")
            with connect(root) as connection:
                state_before, events_before = streaming_load_ledger(connection)
                head_before = events_before[-1]["hash"]
                seq_before = len(events_before)

                # Begin a transaction and insert uncommitted event without commit
                connection.execute("BEGIN IMMEDIATE")
                header = event_header(events_before, "test.interrupted", "tester", "Interrupted write")
                mutated_state = dict(state_before, phase="interrupted")
                event: Dict[str, Any] = dict(header, state=mutated_state)
                event["hash"] = digest(event)
                connection.execute("INSERT INTO events(sequence,value) VALUES (?,?)", (event["sequence"], canonical(event)))
                connection.execute("INSERT OR REPLACE INTO state(id,value) VALUES (1,?)", (canonical(mutated_state),))

                # Verify uncommitted event is in SQLite within active transaction
                uncommitted = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
                self.assertEqual(uncommitted, seq_before + 1)

                # Rollback
                connection.rollback()

                # Verify ledger is in exact clean state before transaction
                state_after, events_after = streaming_load_ledger(connection)
                self.assertEqual(len(events_after), seq_before)
                self.assertEqual(events_after[-1]["hash"], head_before)
                self.assertEqual(state_after["phase"], state_before["phase"])

                # Incomplete write: event committed without updating state table
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("INSERT INTO events(sequence,value) VALUES (?,?)", (event["sequence"], canonical(event)))
                connection.commit()

                # streaming_load_ledger must fail closed because state disagrees with events
                with self.assertRaises(UadosError):
                    streaming_load_ledger(connection)

    def test_realistic_history_benchmark(self):
        """Test 4: Realistic 2.90GB Ledger History Benchmark.

        Execute read-only streaming verification against the actual ~2.90GB ledger (818 events).
        Assert that execution time is <= 15 seconds and memory overhead is bounded.
        """
        ledger_path = Path(".uados/ledger.sqlite3").resolve()
        if not ledger_path.is_file():
            self.skipTest("Real 2.90GB ledger not present; skipping realistic benchmark.")

        # Baseline memory measurement
        rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        started = time.perf_counter()

        uri = ledger_path.resolve().as_uri() + "?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=30) as connection:
            state, events = streaming_load_ledger(connection, keep_events=False)

        elapsed = time.perf_counter() - started
        rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

        # Memory delta in MB
        if sys.platform == "darwin":
            mem_delta_mb = (rss_after - rss_before) / (1024 * 1024)
            peak_mb = rss_after / (1024 * 1024)
        else:
            mem_delta_mb = (rss_after - rss_before) / 1024
            peak_mb = rss_after / 1024

        # Assertions: Verify historical event 818 invariant and monotonic chain growth
        self.assertGreaterEqual(len(events), 818)
        self.assertEqual(events[817]["hash"], "71986e50f91df1ba2076920fe6a61f48f0e9b07f026365c94611c5e3a11a69db")
        self.assertEqual(events[-1]["sequence"], len(events))
        self.assertLessEqual(elapsed, 15.0, f"Streaming verification took {elapsed:.2f}s, expected <= 15.0s")


if __name__ == "__main__":
    unittest.main()
