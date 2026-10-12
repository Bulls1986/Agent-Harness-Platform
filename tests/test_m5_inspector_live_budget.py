"""The Inspector E2E verifier must outlive its native Cube/Worker budget."""
import unittest

from poc.closed_loop.trusted_scenario_runner import NATIVE_B03_TIMEOUT_SECONDS
from poc.closed_loop.verify_trusted_scenario_api_live import (
    INSPECTOR_EVIDENCE_DEADLINE_SECONDS,
)


class InspectorNativeBudgetContractTests(unittest.TestCase):
    def test_api_evidence_deadline_exceeds_actual_native_runner_deadline(self):
        self.assertGreaterEqual(
            INSPECTOR_EVIDENCE_DEADLINE_SECONDS,
            NATIVE_B03_TIMEOUT_SECONDS + 30,
        )


if __name__ == "__main__":
    unittest.main()
