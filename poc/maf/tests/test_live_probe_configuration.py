"""G3 configuration: environment credentials precede optional stdin; never echo secrets."""
from __future__ import annotations

import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify_live_model_protocol import main, read_api_key


class NotReadableStdin:
    def isatty(self):
        return False

    def readline(self):
        raise AssertionError("stdin must never be accessed with env-based credential")


class TtyStdin:
    def isatty(self):
        return True

    def readline(self):
        raise AssertionError("interactive stdin must not be read implicitly")


class EnvironmentCredentialTests(unittest.TestCase):
    def test_environment_key_has_priority_and_does_not_read_stdin(self):
        with patch.dict(os.environ, {"POC_LITELLM_API_KEY": "test-env-key"}), \
             patch("sys.stdin", NotReadableStdin()):
            self.assertEqual(read_api_key(), "test-env-key")

    def test_optional_noninteractive_stdin_fallback(self):
        with patch.dict(os.environ, {"POC_LITELLM_API_KEY": ""}), \
             patch("sys.stdin", io.StringIO("test-stdin-key\n")):
            self.assertEqual(read_api_key(), "test-stdin-key")

    def test_missing_key_never_blocks_interactive_console(self):
        with patch.dict(os.environ, {"POC_LITELLM_API_KEY": ""}), \
             patch("sys.stdin", TtyStdin()):
            self.assertEqual(read_api_key(), "")

    def test_missing_configuration_is_reported_without_secret_values(self):
        output = io.StringIO()
        with patch.dict(os.environ, {
            "POC_POSTGRES_DSN": "", "POC_LITELLM_API_KEY": "",
            "POC_LITELLM_MODEL": "", "POC_LITELLM_BASE_URL": "",
        }), patch("sys.argv", ["verify_live_model_protocol.py"]), \
             patch("sys.stdin", TtyStdin()), patch("sys.stdout", output):
            self.assertEqual(main(), 2)
        result = json.loads(output.getvalue())
        self.assertEqual(result["outcome"], "SETUP_GAP")
        self.assertEqual(set(result["missing_environment_or_arg"]), {
            "POC_POSTGRES_DSN", "POC_LITELLM_API_KEY",
            "POC_LITELLM_MODEL", "POC_LITELLM_BASE_URL",
        })

    def test_environment_model_base_url_and_key_do_not_require_argv(self):
        output = io.StringIO()
        with patch.dict(os.environ, {
            "POC_POSTGRES_DSN": "",
            "POC_LITELLM_API_KEY": "test-key-must-not-appear",
            "POC_LITELLM_MODEL": "test-model",
            "POC_LITELLM_BASE_URL": "http://test.invalid/v1",
        }), patch("sys.argv", ["verify_live_model_protocol.py"]), \
             patch("sys.stdin", NotReadableStdin()), patch("sys.stdout", output):
            self.assertEqual(main(), 2)
        result = json.loads(output.getvalue())
        self.assertEqual(result["missing_environment_or_arg"], ["POC_POSTGRES_DSN"])
        self.assertNotIn("test-key-must-not-appear", output.getvalue())


if __name__ == "__main__":
    unittest.main()
