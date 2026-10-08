"""C09 real PostgreSQL contract tests, no private model requests."""
from __future__ import annotations
from dataclasses import replace
import os
import sys
import unittest
from pathlib import Path
from uuid import uuid4
import psycopg
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from runtime_swap_facts import RuntimeFacts,RuntimeRun


@unittest.skipUnless(os.environ.get("POC_C_PLATFORM_DSN"),
                     "real Harness PostgreSQL required")
class RealRuntimeSwapContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store=RuntimeFacts(os.environ["POC_C_PLATFORM_DSN"])
        cls.store.initialize()

    def fixture(self):
        run=RuntimeRun.build()
        self.store.prepare(run)
        return run,run.request()

    def test_two_frozen_sdk_stages_and_immutable_native_mapping(self):
        run,request=self.fixture()
        self.assertNotEqual(run.run_id,run.native_workflow_id)
        self.assertEqual(tuple(x.adapter for x in run.stages),
                         ("maf-harness","openai-agents"))
        for stage in request["stages"]:
            self.store.require_frozen(request,stage)
        for field in ("native_workflow_id","frozen_workflow_version","expected_marker"):
            forged=request|{field:"forged"}
            with self.subTest(field=field),self.assertRaises(ValueError):
                self.store.require_frozen(forged,request["stages"][0])
        for field in ("adapter","frozen_runtime_version","execution_id","step_id","ordinal"):
            bad=request["stages"][0]|{field:"fake" if field!="ordinal" else 2}
            with self.subTest(field=field),self.assertRaises(ValueError):
                self.store.require_frozen(request,bad)
        with psycopg.connect(self.store.dsn) as db:
            with self.assertRaises(psycopg.Error):
                db.execute("UPDATE poc_c09_runtime_stages SET adapter='openai-agents' "
                           "WHERE attempt_id=%s",(run.stages[0].attempt_id,))

    def test_independent_verifier_idempotency_and_stable_events(self):
        run,request=self.fixture()
        self.assertEqual(self.store.snapshot(run.run_id)["run"]["state"],"RUNNING")
        with self.assertRaises(ValueError):
            self.store.complete(run.run_id) # both are not verified
        for stage in request["stages"]:
            first=self.store.verify(run.run_id,stage,run.expected_marker,22)
            second=self.store.verify(run.run_id,stage,run.expected_marker,22)
            self.assertTrue(first["passed"])
            self.assertTrue(second["idempotent_read"])
        self.assertEqual(self.store.complete(run.run_id)["state"],"COMPLETED")
        self.assertTrue(self.store.complete(run.run_id)["idempotent_read"])
        snap=self.store.snapshot(run.run_id)
        self.assertEqual([row["state"] for row in snap["stages"]],
                         ["SUCCEEDED","SUCCEEDED"])
        self.assertEqual([x["event_type"] for x in snap["events"]],
                         ["run.started","activity.completed","verification.passed",
                          "activity.completed","verification.passed","run.terminal"])
        self.assertEqual([x["seq"] for x in snap["events"]],list(range(1,7)))

    def test_failed_verification_never_finalizes_success(self):
        run,request=self.fixture()
        failed=self.store.verify(run.run_id,request["stages"][0],"C09-00000000",12)
        self.assertFalse(failed["passed"])
        with self.assertRaises(ValueError):
            self.store.complete(run.run_id)
        self.assertEqual(self.store.fail(run.run_id)["state"],"FAILED")
        self.assertTrue(self.store.fail(run.run_id)["idempotent_read"])
        snap=self.store.snapshot(run.run_id)
        self.assertEqual(snap["run"]["state"],"FAILED")
        self.assertEqual(snap["stages"][0]["state"],"FAILED")
        self.assertEqual(snap["stages"][1]["state"],"CANCELLED")


if __name__=="__main__":
    unittest.main()
