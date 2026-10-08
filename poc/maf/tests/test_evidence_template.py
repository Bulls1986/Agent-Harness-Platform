"""Evidence template is structurally complete and must never imply execution PASS."""
import json
import unittest
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1] / "evidence-template.json"
REQUIRED = {
    "schema_version", "task_id", "scenario_id", "gate_ids", "status",
    "recorded_at_utc", "commit_sha", "sdk_versions", "python_version",
    "execution_command", "exit_code", "observed_result",
    "reproducible_evidence_refs", "limitations"
}

class EvidenceTemplateTests(unittest.TestCase):
    def test_template_is_complete_and_initially_unrun(self):
        report = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        self.assertFalse(REQUIRED - report.keys())
        self.assertEqual(report["status"], "NOT_RUN")
        self.assertIsNone(report["exit_code"])
        self.assertEqual(report["reproducible_evidence_refs"], [])
        self.assertTrue(report["limitations"])

if __name__ == "__main__":
    unittest.main()
