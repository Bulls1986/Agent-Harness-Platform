"""SDK argument contract regression; no real Cube or PG is involved.

The actual DEV-M5 live gate remains mandatory and is not satisfied by this test.
"""
import os
import sys
import types
import unittest
from unittest.mock import patch

from poc.sandbox.cube_binding import NativeCubeTransport


class NativeCubeCreateTests(unittest.TestCase):
    def test_create_uses_explicit_frozen_template_and_metadata(self):
        calls = []

        class FakeSandbox:
            @classmethod
            def create(cls, **kwargs):
                calls.append(kwargs)
                return types.SimpleNamespace(sandbox_id="native-sandbox-1")

        sdk = types.ModuleType("cubesandbox")
        sdk.Sandbox = FakeSandbox
        with patch.dict(sys.modules, {"cubesandbox": sdk}):
            with patch.dict(os.environ, {
                "CUBE_API_URL": "http://127.0.0.1:3000",
                "CUBE_TEMPLATE_ID": "frozen-template-a",
            }):
                adapter = NativeCubeTransport()
                # A later unrelated request cannot silently change the template
                # of the original provider adapter.
                os.environ["CUBE_TEMPLATE_ID"] = "different-template"
                metadata = {"harness_execution_id": "synthetic-exec"}
                self.assertEqual(adapter.create(metadata=metadata), "native-sandbox-1")
                self.assertEqual(metadata, {"harness_execution_id": "synthetic-exec"})
        self.assertEqual(calls, [{
            "template": "frozen-template-a",
            "timeout": 300,
            "metadata": {"harness_execution_id": "synthetic-exec"},
        }])

    def test_missing_template_rejects_before_provider_import_or_call(self):
        with patch.dict(os.environ, {"CUBE_API_URL": "http://127.0.0.1:3000"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "CUBE_TEMPLATE_ID"):
                NativeCubeTransport()


if __name__ == "__main__":
    unittest.main()
