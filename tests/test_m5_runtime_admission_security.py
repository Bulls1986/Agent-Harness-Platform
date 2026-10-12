"""DEV-M5 exit: deny implicit or misdeclared execution capabilities.

The operation name is untrusted and cannot bypass Sandbox admission merely
because a client supplied capabilities={'model'}.
"""
import unittest
from dataclasses import replace

from poc.runtime_spi.contract import (
    AgentRuntimeDispatcher, ExecutionContext, RunRequest, RuntimeAdmissionDenied,
    SandboxGrant,
)


class RecordingExecutor:
    name = "native-test-executor"
    operations = frozenset({"model.run", "shell.exec", "files.write", "git.status"})

    def __init__(self):
        self.invocations = 0

    async def invoke(self, request, emit, cancellation):
        self.invocations += 1
        return "ok"


class AdmissionSecurityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.context = ExecutionContext(
            run_id="r", turn_id="t", session_id="s",
            isolation_scope="project:alpha", execution_id="e",
            owner_id="worker-b", fencing_token=8, workspace_ref="w",
        )
        self.grant = SandboxGrant(
            sandbox_id="real-cube", isolation_scope="project:alpha",
            execution_id="e", owner_id="worker-b", fencing_token=8,
            lease_id="pg-lease", capabilities=frozenset({"shell", "files", "git"}),
        )
        self.adapter = RecordingExecutor()
        self.dispatcher = AgentRuntimeDispatcher(self.adapter)

    async def test_native_tool_action_cannot_hide_behind_model_capability(self):
        for action in ("shell.exec", "files.write", "git.status"):
            with self.subTest(action=action), self.assertRaises(RuntimeAdmissionDenied):
                await self.dispatcher.execute(RunRequest(
                    self.context, self.adapter.name, "test",
                    operation=action, capabilities=frozenset({"model"}),
                    sandbox=self.grant,
                ))
        self.assertEqual(self.adapter.invocations, 0)

    async def test_native_tool_cannot_execute_without_lease(self):
        for action, capability in (
                ("shell.exec", "shell"), ("files.write", "files"), ("git.status", "git")):
            with self.subTest(action=action), self.assertRaises(RuntimeAdmissionDenied):
                await self.dispatcher.execute(RunRequest(
                    self.context, self.adapter.name, "test", operation=action,
                    capabilities=frozenset({capability}),
                ))
        self.assertEqual(self.adapter.invocations, 0)

    async def test_stale_cross_scope_and_insufficient_grant_never_reach_adapter(self):
        for wrong in (
            replace(self.grant, fencing_token=7),
            replace(self.grant, isolation_scope="project:other"),
            replace(self.grant, owner_id="worker-a"),
            replace(self.grant, capabilities=frozenset({"files", "git"})),
        ):
            with self.subTest(wrong=wrong), self.assertRaises(RuntimeAdmissionDenied):
                await self.dispatcher.execute(RunRequest(
                    self.context, self.adapter.name, "test", operation="shell.exec",
                    capabilities=frozenset({"shell"}), sandbox=wrong,
                ))
        self.assertEqual(self.adapter.invocations, 0)

    async def test_unknown_capability_is_not_implicitly_trusted(self):
        with self.assertRaises(RuntimeAdmissionDenied):
            await self.dispatcher.execute(RunRequest(
                self.context, self.adapter.name, "test",
                operation="model.run", capabilities=frozenset({"superuser"}),
            ))
        self.assertEqual(self.adapter.invocations, 0)

    async def test_model_only_runs_without_allocating_or_needing_cube(self):
        events = await self.dispatcher.execute(RunRequest(
            self.context, self.adapter.name, "test", operation="model.run",
            capabilities=frozenset({"model"}), sandbox=None,
        ))
        self.assertEqual(events[-1].type, "run.completed")
        self.assertEqual(self.adapter.invocations, 1)

    async def test_trusted_native_action_permits_matching_fenced_grant(self):
        events = await self.dispatcher.execute(RunRequest(
            self.context, self.adapter.name, "test", operation="shell.exec",
            capabilities=frozenset({"shell"}), sandbox=self.grant,
        ))
        self.assertEqual(events[-1].type, "run.completed")
        self.assertEqual(self.adapter.invocations, 1)


if __name__ == "__main__":
    unittest.main()
