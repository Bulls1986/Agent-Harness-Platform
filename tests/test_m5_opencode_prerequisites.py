"""Unit checks for the fixed native Guest prereq probe (not a Fake Cube PASS)."""
import unittest
from unittest.mock import Mock

from poc.sandbox.verify_opencode_guest_prerequisites import (
    REQUIRED, OPTIONAL, check_prerequisites,
)


class GuestPrerequisiteTests(unittest.TestCase):
    def test_all_tools_must_be_observed_in_guest(self):
        guest = Mock()
        guest.commands.run.side_effect = [
            Mock(exit_code=0, stdout="/usr/bin/" + name)
            for name in REQUIRED + OPTIONAL
        ] + [Mock(exit_code=0, stdout="1.1.0")]
        result = check_prerequisites(guest)
        self.assertTrue(all(result.values()))
        self.assertEqual(guest.commands.run.call_count, len(REQUIRED + OPTIONAL) + 1)
        for call in guest.commands.run.call_args_list:
            self.assertIn(call.kwargs["timeout"], (12,15))
            self.assertTrue(call.args[0].startswith("command -v ")
                            or call.args[0] == "opencode --version")

    def test_missing_opencode_or_empty_output_is_explicitly_unready(self):
        guest = Mock()
        guest.commands.run.side_effect = [
            Mock(exit_code=0, stdout="/usr/bin/" + name)
            for name in REQUIRED[:-1]
        ] + [Mock(exit_code=1, stdout="")] + [
            Mock(exit_code=0, stdout="/usr/bin/" + name) for name in OPTIONAL]
        result = check_prerequisites(guest)
        self.assertFalse(result["opencode"])
        self.assertFalse(result["opencode_version_works"])
        self.assertTrue(all(result[n] for n in REQUIRED[:-1]))

    def test_success_exit_without_real_path_is_not_ready(self):
        guest = Mock()
        guest.commands.run.side_effect = [
            Mock(exit_code=0, stdout="") for _ in REQUIRED + OPTIONAL
        ]
        self.assertFalse(any(check_prerequisites(guest).values()))

    def test_standalone_opencode_requires_no_node_or_npm(self):
        guest = Mock()
        guest.commands.run.side_effect = [
            Mock(exit_code=0, stdout="/usr/bin/" + name)
            for name in REQUIRED
        ] + [Mock(exit_code=1, stdout=""), Mock(exit_code=1, stdout=""),
             Mock(exit_code=0, stdout="v2") ]
        result = check_prerequisites(guest)
        self.assertFalse(result["node"])
        self.assertFalse(result["npm"])
        self.assertTrue(result["opencode_version_works"])


if __name__ == "__main__":
    unittest.main()
