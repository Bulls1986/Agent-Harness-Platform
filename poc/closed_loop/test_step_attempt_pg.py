"""DEV-M3: PG Attempt identity is mandatory; provider retry is NOT automatic re-execution."""
import os
import unittest
from uuid import uuid4

from poc.closed_loop.facts import PgFacts, UnsafeDispatch
from poc.runtime_spi.contract import TypedEvent


@unittest.skipUnless(os.getenv("HARNESS_POC_DATABASE_URL"),
                     "Real PostgreSQL required; skipped tests do not prove live gate")
class StepAttemptFactsTests(unittest.TestCase):
    def setUp(self):
        self.db = PgFacts()
        self.run = "m3-attempt-" + uuid4().hex
        cmd = self.db.create(self.run, prompt="synthetic")
        self.db.dispatch(cmd)
        self.db.bind(cmd, "provider-" + self.run)
        self.first = "attempt-" + uuid4().hex
        self.other = "attempt-" + uuid4().hex

    def events(self, output="ok"):
        return [TypedEvent(self.run, 1, "run.completed",
                           "pydantic", {"result": output})]

    def test_valid_attempt_is_persisted_and_commits_exactly_once(self):
        self.assertIsNone(self.db.start_step(
            self.run, "pydantic", "synthetic", attempt_id=self.first))
        self.db.finish_step(self.run, "pydantic", "ok", self.events(),
                            attempt_id=self.first)
        with PgFacts().tx() as c:
            row = c.execute(
                "SELECT attempt_id,plan_version,ordinal,state FROM harness_step_attempt "
                "WHERE run_id=%s AND step_id='pydantic'", (self.run,)
            ).fetchone()
        self.assertEqual(row, (self.first, 1, 1, "COMPLETED"))
        self.assertEqual(self.db.start_step(self.run, "pydantic", "synthetic",
                                             attempt_id=self.other), "ok")
        with self.assertRaises(UnsafeDispatch):
            self.db.finish_step(self.run, "pydantic", "duplicate", self.events(),
                                attempt_id=self.first)
        self.assertEqual(self.db.snapshot(self.run)["steps"]["pydantic"]["attempts"], 1)

    def test_parallel_or_replayed_start_never_reinvokes_sdk(self):
        self.db.start_step(self.run, "pydantic", "synthetic", attempt_id=self.first)
        before = self.db.snapshot(self.run)
        with self.assertRaises(UnsafeDispatch):
            PgFacts().start_step(self.run, "pydantic", "synthetic", attempt_id=self.other)
        with self.assertRaises(UnsafeDispatch):
            self.db.start_step(self.run, "pydantic", "synthetic", attempt_id=self.first)
        after = self.db.snapshot(self.run)
        self.assertEqual(before["steps"], after["steps"])
        self.assertEqual(before["events"], after["events"])

    def test_wrong_or_missing_attempt_cannot_complete(self):
        self.db.start_step(self.run, "pydantic", "synthetic", attempt_id=self.first)
        before = self.db.snapshot(self.run)
        with self.assertRaises(UnsafeDispatch):
            self.db.finish_step(self.run, "pydantic", "wrong", self.events(),
                                attempt_id=self.other)
        with self.assertRaises((TypeError, UnsafeDispatch)):
            self.db.finish_step(self.run, "pydantic", "unfenced", self.events())
        with self.assertRaises(UnsafeDispatch):
            self.db.finish_step(self.run, "openai", "cross-step", self.events(),
                                attempt_id=self.first)
        self.assertEqual(self.db.snapshot(self.run)["events"], before["events"])
        self.assertEqual(self.db.snapshot(self.run)["steps"], before["steps"])

    def test_invalid_attempt_identifier_rejected_without_execution(self):
        for invalid in ("", " ", "x" * 129):
            with self.assertRaises((ValueError, UnsafeDispatch)):
                self.db.start_step(self.run, "pydantic", "synthetic",
                                   attempt_id=invalid)
        self.assertEqual(self.db.snapshot(self.run)["steps"]["pydantic"]["attempts"], 0)

    def test_cancelled_run_blocks_original_attempt_commit(self):
        self.db.start_step(self.run, "pydantic", "synthetic", attempt_id=self.first)
        self.db.request_cancel(self.run)
        with self.assertRaises(UnsafeDispatch):
            self.db.finish_step(self.run, "pydantic", "late", self.events(),
                                attempt_id=self.first)
        self.db.acknowledge_cancel(self.run)
        with self.assertRaises(UnsafeDispatch):
            self.db.finish_step(self.run, "pydantic", "late", self.events(),
                                attempt_id=self.first)
        self.assertEqual(self.db.snapshot(self.run)["state"], "CANCELLED")


if __name__ == "__main__":
    unittest.main()