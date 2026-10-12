"""No-DB rejection regression for a wrong native Cube connect() identity.

Real PostgreSQL and real Cube must still be verified at the live gate.
"""
import types
import unittest

from poc.closed_loop.facts import UnsafeDispatch
from poc.sandbox.cube_binding import CubeWorkspaceGateway


class Binding:
    def assert_active(self, *args):
        return types.SimpleNamespace(sandbox_id="original-cube", generation=1)


class WrongNativeConnect:
    def __init__(self, returned):
        self.returned = returned
        self.data_reads = 0
        self.data_writes = 0

    def connect(self, sandbox_id):
        assert sandbox_id == "original-cube"
        return self.returned

    def read(self, *args):
        self.data_reads += 1
        return "untrusted-data"

    def write(self, *args):
        self.data_writes += 1


class NativeCubeIdentityTests(unittest.TestCase):
    def test_wrong_native_sdk_identity_is_rejected_before_guest_access(self):
        for wrong in (
            types.SimpleNamespace(sandbox_id="different-cube"),
            types.SimpleNamespace(),
            "different-cube",
        ):
            with self.subTest(wrong=wrong):
                transport = WrongNativeConnect(wrong)
                gateway = CubeWorkspaceGateway(Binding(), transport)
                with self.assertRaises(UnsafeDispatch):
                    gateway.read("exec-1", "worker-B", 8, "/workspace/test.txt")
                with self.assertRaises(UnsafeDispatch):
                    gateway.write("exec-1", "worker-B", 8,
                                  "/workspace/test.txt", "new")
                self.assertEqual(transport.data_reads, 0)
                self.assertEqual(transport.data_writes, 0)

    def test_matching_native_sdk_identity_allows_guest_access(self):
        transport = WrongNativeConnect(
            types.SimpleNamespace(sandbox_id="original-cube"))
        gateway = CubeWorkspaceGateway(Binding(), transport)
        self.assertEqual(gateway.read(
            "exec-1", "worker-B", 8, "/workspace/test.txt"), "untrusted-data")
        self.assertEqual(transport.data_reads, 1)


if __name__ == "__main__":
    unittest.main()
