"""Single actual Run: v1 failed verifier -> immutable v2 -> trusted PASS."""
import asyncio
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bounded_replan import run_bounded_document_replan
from task_ledger import TaskLedger


@unittest.skipUnless(os.environ.get("POC_POSTGRES_DSN"),"dedicated real PostgreSQL")
class DeterministicReplanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger=TaskLedger(os.environ["POC_POSTGRES_DSN"])
        cls.ledger.initialize()

    def test_real_maf_two_workflows_same_run_plan_v2_and_exactly_one_terminal(self):
        result=asyncio.run(run_bounded_document_replan(self.ledger))
        self.assertEqual(result["run"]["state"],"COMPLETED")
        self.assertEqual([x["version"] for x in result["plans"]],[1,2])
        self.assertEqual(result["plans"][1]["parent_plan_id"],
                         result["plans"][0]["plan_id"])
        self.assertEqual([x["state"] for x in result["attempts"]],
                         ["FAILED","SUCCEEDED"])
        self.assertNotEqual(result["attempts"][0]["attempt_id"],
                            result["attempts"][1]["attempt_id"])
        self.assertEqual([x["passed"] for x in result["verifications"]],
                         [False,True])
        self.assertEqual(
            [(x["seq"],x["event_type"]) for x in result["events"]],
            [(1,"run.started"),(2,"verification.failed"),
             (3,"plan.replanned"),(4,"run.terminal")],
        )
        readback=TaskLedger(self.ledger.dsn).read(result["run"]["run_id"])
        self.assertEqual(readback,result)
