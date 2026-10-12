"""Physical Hatchet native OpenCode joint proof is never inferred from B03."""
import unittest

from poc.sandbox.verify_hatchet_cube_worker_takeover import (
    validate_opencode_joint_evidence,
)


class PhysicalOpenCodeJointEvidenceTests(unittest.TestCase):
    def test_all_real_native_session_guest_claims_required(self):
        good = {
            "native_opencode_session_id": "ses_aaa123",
            "native_opencode_session_after_retry": "ses_aaa123",
            "opencode_shell_files_git": True,
            "opencode_original_guest_file_preserved": True,
            "opencode_old_owner_denied": True,
            "opencode_pg_effect_receipts_confirmed": 2,
            "opencode_pg_effects_pending": 0,
            "opencode_destroy_ack": "RELEASED",
        }
        validate_opencode_joint_evidence(good)
        for name in good:
            missing = dict(good)
            del missing[name]
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_opencode_joint_evidence(missing)
        with self.assertRaises(ValueError):
            validate_opencode_joint_evidence({
                **good, "native_opencode_session_after_retry": "ses_other"})
        with self.assertRaises(ValueError):
            validate_opencode_joint_evidence({
                **good, "opencode_original_guest_file_preserved": "true"})
        with self.assertRaises(ValueError):
            validate_opencode_joint_evidence({
                **good, "opencode_pg_effects_pending": 1})


if __name__ == "__main__":
    unittest.main()
