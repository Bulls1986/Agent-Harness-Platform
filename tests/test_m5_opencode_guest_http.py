"""OpenCode public Guest API path negotiation, no local Host fallback."""
import unittest
from unittest.mock import Mock

from poc.sandbox.verify_opencode_guest_http import (
    resolve_api_prefix, native_session_id, _guest_http,
)


class OpenCodePublicApiVersionTests(unittest.TestCase):
    def test_open_code_v2_uses_api_namespace(self):
        self.assertEqual(resolve_api_prefix("opencode v2.0.24"), "/api")
        self.assertEqual(resolve_api_prefix("2.1.0"), "/api")

    def test_legacy_v1_can_use_legacy_namespace(self):
        self.assertEqual(resolve_api_prefix("1.2.1"), "")

    def test_unknown_or_malformed_version_blocks_execution(self):
        for version in ("", "nightly", "../v2", "1.2.3 extra", "v3.0.0"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                resolve_api_prefix(version)

    def test_v2_session_is_from_native_data_envelope(self):
        self.assertEqual(
            native_session_id({"data": {"id": "ses_realnative123"}}, "/api"),
            "ses_realnative123",
        )

    def test_v1_session_has_plain_response(self):
        self.assertEqual(native_session_id({"id": "ses_legacy"}, ""), "ses_legacy")

    def test_missing_ambiguous_or_invalid_session_identity_fails_closed(self):
        for response, prefix in (
                ({"data": {}}, "/api"),
                ({"data": {"id": "../../foo"}}, "/api"),
                ({"id": "client-forged", "data": {"id": "native"}}, "/api"),
                ({"id": "plain"}, "/api"),
                ({"data": {"id": "ses_other"}}, ""),
                ([], "/api"),
        ):
            with self.subTest(response=response, prefix=prefix), self.assertRaises(ValueError):
                native_session_id(response, prefix)

    def test_native_file_api_only_allows_canonical_guest_workspace(self):
        guest = Mock()
        guest.commands.run.return_value = Mock(
            exit_code=0, stdout='{"data":{"type":"text","content":"synthetic"}}')
        route = ("/api/file/content?path=%2Fworkspace%2F"
                 "m5-opencode%2Fnative-tool.txt")
        self.assertEqual(
            _guest_http(guest, "synthetic-private-secret-1234567890",
                        "GET", route)["data"]["content"],
            "synthetic",
        )
        for path in (
                "/api/file/content?path=%2Fetc%2Fpasswd",
                "/api/file/content?path=%2Fworkspace%2F..%2Fetc",
                "/api/file/content?path=%2Fworkspace%2Fok&command=whoami",
        ):
            with self.subTest(path=path), self.assertRaises(ValueError):
                _guest_http(guest, "synthetic-private-secret-1234567890",
                            "GET", path)
        self.assertEqual(guest.commands.run.call_count, 1)

    def test_native_v2_files_read_is_relative_and_returns_real_bytes(self):
        guest = Mock()
        guest.commands.run.return_value = Mock(
            exit_code=0, stdout="synthetic-file-content")
        result = _guest_http(
            guest, "synthetic-private-secret-1234567890",
            "GET", "/api/fs/read/native-tool.txt")
        self.assertEqual(result, "synthetic-file-content")
        for unsafe_path in ("/api/fs/read/../etc/passwd",
                            "/api/fs/read/%2E%2E%2Fsecret",
                            "/api/fs/read/../../runtime",
                            "/api/fs/read/.."):
            with self.subTest(unsafe_path=unsafe_path), self.assertRaises(ValueError):
                _guest_http(
                    guest, "synthetic-private-secret-1234567890",
                    "GET", unsafe_path)


if __name__ == "__main__":
    unittest.main()
