"""Offline native MAF Workflow execution; deterministic terminal status contract."""
import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from workflow_probe import VerificationFact, execute_fact


class NativeWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_success_requires_evidence_and_preserves_platform_ids(self):
        fact = VerificationFact.example(passed=True, evidence_ref="evidence://poc/ok")
        result = await execute_fact(fact)
        self.assertEqual(result.run_state, "COMPLETED")
        self.assertEqual(result.verification_state, "SUCCEEDED")
        self.assertEqual(
            (result.run_id, result.plan_id, result.step_id, result.attempt_id, result.plan_version),
            (fact.run_id, fact.plan_id, fact.step_id, fact.attempt_id, fact.plan_version)
        )

    async def test_verifier_failure_stays_failed(self):
        outcome = await execute_fact(VerificationFact.example(
            passed=False, evidence_ref="evidence://poc/failed"
        ))
        self.assertEqual(outcome.run_state, "FAILED")
        self.assertEqual(outcome.verification_state, "VERIFICATION_FAILURE")

    async def test_no_evidence_never_completes(self):
        outcome = await execute_fact(VerificationFact.example(
            passed=True, evidence_ref=None
        ))
        self.assertEqual(outcome.run_state, "FAILED")

    async def test_invalid_plan_version_is_rejected(self):
        fact = replace(VerificationFact.example(
            passed=True, evidence_ref="evidence://poc/ok"
        ), plan_version=0)
        with self.assertRaises(Exception):
            await execute_fact(fact)


if __name__ == "__main__":
    unittest.main()
