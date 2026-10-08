"""Fast public MAF Executor -> Harness gate -> Tool Adapter contract, no Docker/DB.

The database transaction itself is tested separately with real PostgreSQL.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from execution_ownership import Ownership, StaleExecutionOwner
from maf_execution_adapter import GuardedToolRequest, build_guarded_tool_workflow


class InMemoryAdmissionStub:
    def __init__(self):
        self.dispatched = set()

    def dispatch(self, ownership):
        key = (ownership.execution_id, ownership.owner_id, ownership.fencing_token)
        if key in self.dispatched:
            raise StaleExecutionOwner("Repeated dispatch")
        self.dispatched.add(key)


class NativeMafToolAdmissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_replayed_maf_executor_rejects_second_adapter_call(self):
        gate = InMemoryAdmissionStub()
        calls = []

        async def tool(payload):
            calls.append(payload)
            return "tool-result"

        request = GuardedToolRequest(Ownership("execution-poc", "A", 1), "write")
        first = await build_guarded_tool_workflow(gate, tool).run(request)
        self.assertEqual(first.get_outputs(), ["tool-result"])
        try:
            await build_guarded_tool_workflow(gate, tool).run(request)
        except StaleExecutionOwner:
            pass
        self.assertEqual(calls, ["write"])
        self.assertEqual(len(gate.dispatched), 1)

    async def test_crash_after_admission_does_not_call_tool_again(self):
        gate = InMemoryAdmissionStub()
        calls = []

        async def crash(payload):
            calls.append(payload)
            raise RuntimeError("downstream result unknown")

        request = GuardedToolRequest(Ownership("execution-crash", "A", 1), "write")
        try:
            await build_guarded_tool_workflow(gate, crash).run(request)
        except RuntimeError:
            pass
        self.assertEqual(calls, ["write"])
        try:
            await build_guarded_tool_workflow(gate, crash).run(request)
        except StaleExecutionOwner:
            pass
        self.assertEqual(calls, ["write"])


if __name__ == "__main__":
    unittest.main()
