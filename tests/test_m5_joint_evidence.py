"""Fail-closed verifier contract for a single-run M5 physical+Cube live proof.

These unit tests do not attest that a real worker or MicroVM was run.
"""
import unittest

from poc.sandbox.joint_gate_contract import validate_joint_evidence


def example():
    return {
        "run_id": "run-1", "execution_id": "execution-1",
        "workflow_run_id": "workflow-1",
        "worker_a_pid": 100, "worker_a_exit_code": -9,
        "worker_b_pid": 200, "b_worker_role": "worker-B",
        "native_retry_count": 1, "initial_epoch": 7, "new_epoch": 8,
        "a_cube_id": "cube-1", "b_cube_id": "cube-1",
        "guest_original": "test-guest-bytes",
        "guest_after_reconnect": "test-guest-bytes",
        "old_epoch_rejected": True, "wrong_scope_rejected": True,
        "destroy_ack": "RELEASED",
    }


class JointEvidenceContractTests(unittest.TestCase):
    def test_all_correlated_fields_are_required(self):
        validate_joint_evidence(example())

    def test_no_combining_unrelated_workflows_or_sandboxes(self):
        for key, value in (
            ("workflow_run_id", ""),
            ("b_cube_id", "a-different-sandbox"),
            ("guest_after_reconnect", "reconstructed-file"),
            ("worker_b_pid", 100),
            ("native_retry_count", 0),
            ("worker_a_exit_code", 0),
            ("old_epoch_rejected", False),
            ("wrong_scope_rejected", False),
            ("destroy_ack", "UNKNOWN"),
            ("new_epoch", 7),
        ):
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_joint_evidence({**example(), key: value})

    def test_missing_claims_never_count_as_pass(self):
        proof = example()
        for key in ("run_id", "execution_id", "a_cube_id", "guest_original"):
            with self.subTest(key=key):
                data = {**proof}
                del data[key]
                with self.assertRaises(ValueError):
                    validate_joint_evidence(data)


if __name__ == "__main__":
    unittest.main()
