"""Acceptance correctness tests using only committed trusted fixtures."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify_fixture import ROOT, expected_document, verify_coding, verify_document

class VerifierTests(unittest.TestCase):
    def test_coding_bad_must_fail(self):
        result = verify_coding(ROOT / "coding" / "buggy")
        self.assertFalse(result["passed"])
        self.assertEqual(result["classification"], "VERIFICATION_FAILURE")

    def test_coding_reference_passes(self):
        self.assertTrue(verify_coding(ROOT / "coding" / "solution")["passed"])

    def test_missing_candidate_fails(self):
        self.assertFalse(verify_coding(ROOT / "coding" / "absent")["passed"])

    def test_document_bad_must_fail(self):
        result = verify_document(ROOT / "document" / "buggy")
        self.assertFalse(result["passed"])
        self.assertEqual(result["classification"], "VERIFICATION_FAILURE")

    def test_document_reference_passes(self):
        self.assertTrue(verify_document(ROOT / "document" / "expected")["passed"])

    def test_document_expected_matches_source(self):
        import json
        expected = json.loads((ROOT / "document" / "expected" / "summary.json").read_text())
        self.assertEqual(expected, expected_document())

if __name__ == "__main__":
    unittest.main()
