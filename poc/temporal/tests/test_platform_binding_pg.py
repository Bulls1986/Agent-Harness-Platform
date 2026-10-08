"""C07 real PostgreSQL immutable native binding negative contracts."""
from __future__ import annotations

from dataclasses import replace
import os
import sys
import unittest
from pathlib import Path
from uuid import uuid4

import psycopg

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from platform_facts import FrozenTemporal,TemporalTaskFacts,FrozenTemporalMismatch
from execution_ownership import StaleExecutionOwner


@unittest.skipUnless(os.environ.get("POC_C_PLATFORM_DSN"),"Real Harness PostgreSQL required")
class FrozenTemporalBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store=TemporalTaskFacts(os.environ["POC_C_PLATFORM_DSN"])
        cls.store.initialize()

    def fixture(self):
        suffix=uuid4().hex
        b=FrozenTemporal(
            run_id="run-"+suffix,plan_id="plan-"+suffix,
            step_id="step-"+suffix,attempt_id="attempt-"+suffix,
            execution_id="execution-"+suffix,native_workflow_id="temporal-c07-"+suffix)
        self.store.prepare(b)
        return b

    def test_immutable_native_id_identity_and_versions(self):
        b=self.fixture()
        self.store.require_frozen(b)
        snap=self.store.snapshot(b)
        self.assertEqual(snap["run_state"],"RUNNING")
        self.assertEqual(snap["attempt_state"],"RUNNING")
        for field in ("run_id","plan_id","step_id","attempt_id","execution_id",
                      "native_workflow_id","frozen_workflow_version",
                      "frozen_runtime_version"):
            with self.subTest(field=field):
                with self.assertRaises(FrozenTemporalMismatch):
                    self.store.require_frozen(replace(b,**{field:"tampered"}))
        # Database-level immutable trigger: direct SQL cannot rewrite identity.
        with psycopg.connect(self.store.dsn) as conn:
            with self.assertRaises(psycopg.Error):
                conn.execute(
                    "UPDATE poc_c_temporal_bindings SET native_workflow_id=%s "
                    "WHERE execution_id=%s",("forged",b.execution_id))
        with psycopg.connect(self.store.dsn) as conn:
            with self.assertRaises(psycopg.Error):
                conn.execute(
                    "DELETE FROM poc_c_temporal_bindings WHERE execution_id=%s",
                    (b.execution_id,))
        self.store.require_frozen(b)

    def test_no_same_attempt_relaunch_and_no_quarantine_before_dispatch(self):
        b=self.fixture()
        with self.assertRaises(psycopg.Error):
            self.store.prepare(b)
        with self.assertRaises(FrozenTemporalMismatch):
            self.store.quarantine_after_dispatch(b)
        snap=self.store.snapshot(b)
        self.assertIsNone(snap["reconciliation_state"])
        self.assertEqual(snap["attempt_state"],"RUNNING")
        self.assertFalse(snap["dispatch_claimed"])

    def test_live_dispatched_owner_cannot_prematurely_mark_unknown(self):
        b=self.fixture()
        owner=self.store.owner.claim(b.execution_id,owner_id="live-worker",ttl_seconds=30)
        self.store.owner.dispatch(owner)
        with self.assertRaises(FrozenTemporalMismatch):
            self.store.quarantine_after_dispatch(b)
        state=self.store.snapshot(b)
        self.assertEqual(state["attempt_state"],"RUNNING")
        self.assertIsNone(state["reconciliation_state"])

    def test_superseded_plan_cannot_admit_old_native_binding(self):
        b=self.fixture()
        with psycopg.connect(self.store.dsn) as conn:
            conn.execute(
                """INSERT INTO poc_plans(plan_id,run_id,version,parent_plan_id,reason)
                   VALUES (%s,%s,2,%s,'trusted replan invalidates old v1')""",
                ("plan-next-"+uuid4().hex,b.run_id,b.plan_id))
        with self.assertRaises(FrozenTemporalMismatch):
            self.store.require_frozen(b)


if __name__=="__main__":
    unittest.main()
