"""Actual MAF document workflow using trusted files and independent verification."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from document_workflow import run_document_case


class DocumentWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_reference_case_completes_only_after_real_verification(self):
        actual = await run_document_case("expected")
        self.assertEqual(actual.run_state, "COMPLETED")
        self.assertEqual(actual.verification_state, "SUCCEEDED")
        self.assertTrue(actual.run_id.startswith("run-"))
        self.assertTrue(actual.evidence_ref.startswith("poc-fixture://"))

    async def test_deliberately_broken_case_does_not_complete(self):
        actual = await run_document_case("buggy")
        self.assertEqual(actual.run_state, "FAILED")
        self.assertEqual(actual.verification_state, "VERIFICATION_FAILURE")


if __name__ == "__main__":
    unittest.main()
