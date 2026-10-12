"""OpenCode Native API invocations must be scoped through the PG Cube gate.

Mock Guest exercises admission only. It does NOT count as actual OpenCode or
microVM evidence (the explicit Linux live proof does).
"""
import unittest
from unittest.mock import Mock
from unittest.mock import patch

from poc.closed_loop.facts import UnsafeDispatch
from poc.sandbox.opencode_bound_guest import BoundOpenCodeGuest


class OpenCodeGuestScopeTests(unittest.TestCase):
    def setUp(self):
        self.binding = Mock()
        self.guest = Mock()
        self.workspace = Mock()
        self.workspace.binding.assert_active = Mock()
        self.workspace._attach.return_value = self.guest
        self.client = BoundOpenCodeGuest(
            self.workspace, password="synthetic-private-" + "k" * 24)

    def test_version_and_session_always_attach_by_execution_owner_epoch(self):
        self.guest.commands.run.side_effect = [
            Mock(exit_code=0, stdout="opencode v2.0.24"),
            Mock(exit_code=0, stdout='{"data":{"id":"ses_native"}}'),
        ]
        result = self.client.create_session("exec", "worker-A", 7)
        self.assertEqual(result, ("ses_native", "/api"))
        self.assertEqual(self.workspace._attach.call_count, 2)
        self.workspace._attach.assert_any_call("exec", "worker-A", 7)

    def test_stale_epoch_denied_before_any_guest_http_or_shell(self):
        self.workspace._attach.side_effect = UnsafeDispatch("stale")
        with self.assertRaises(UnsafeDispatch):
            self.client.native_shell(
                "exec", "worker-A", 7,
                "ses_native", "/api", "printf synthetic")
        self.assertFalse(self.guest.commands.run.called)

    def test_untrusted_session_id_and_wrong_api_version_rejected(self):
        for session_id, prefix in (
                ("../../another", "/api"),
                ("ses_foo", "/unknown"),
                ("", "/api")):
            with self.subTest(session_id=session_id, prefix=prefix), self.assertRaises(ValueError):
                self.client.native_shell(
                    "exec", "worker-B", 8, session_id, prefix, "echo synthetic")
        self.assertFalse(self.guest.commands.run.called)

    def test_racing_handoff_after_http_is_unknown_not_success(self):
        self.guest.commands.run.return_value = Mock(exit_code=0, stdout="")
        self.workspace.binding.assert_active.side_effect = UnsafeDispatch(
            "taken over during side effect")
        with self.assertRaises(UnsafeDispatch):
            self.client.native_shell(
                "exec", "worker-A", 7, "ses_native", "/api", "echo synthetic")
        self.assertTrue(self.guest.commands.run.called)

    def test_unknown_or_short_credential_is_rejected(self):
        with self.assertRaises(ValueError):
            BoundOpenCodeGuest(self.workspace, password="guess")

    def test_native_files_and_git_require_current_pg_permit(self):
        self.workspace._attach.side_effect = UnsafeDispatch("wrong scope")
        with self.assertRaises(UnsafeDispatch):
            self.client.read_native_file(
                "exec", "worker-A", 7, "/api", "native-tool.txt")
        with self.assertRaises(UnsafeDispatch):
            self.client.native_vcs("exec", "worker-A", 7, "/api")
        self.assertFalse(self.guest.commands.run.called)

    def test_matching_file_without_terminal_receipt_never_confirms_effect(self):
        """Early file writes cannot prove the async Guest Shell has stopped."""
        self.guest.commands.run.return_value = Mock(exit_code=0, stdout="")
        def read_file(_execution, _owner, _epoch, path):
            if path == "/workspace/m5-opencode/a.txt":
                return "expected"
            raise FileNotFoundError(path)
        self.workspace.read.side_effect = read_file
        with patch("poc.sandbox.opencode_bound_guest.time.sleep") as sleep:
            with self.assertRaises(UnsafeDispatch):
                self.client.native_shell_verified_file(
                    "exec","worker-A",7,"ses_native","/api",
                    "printf expected > /workspace/m5-opencode/a.txt",
                    "/workspace/m5-opencode/a.txt","expected")
        self.assertEqual(sleep.call_count,10)
        self.workspace.binding.begin_guest_effect.assert_called_once()
        self.workspace.binding.confirm_guest_effect.assert_not_called()

    def test_shell_http_error_leaves_guest_effect_pending(self):
        self.guest.commands.run.side_effect = ConnectionError("ACK missing")
        with self.assertRaises(ConnectionError):
            self.client.native_shell(
                "exec","worker-A",7,"ses_native","/api",
                "printf x > /workspace/m5-opencode/a.txt")
        self.workspace.binding.begin_guest_effect.assert_called_once()
        self.workspace.binding.confirm_guest_effect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
