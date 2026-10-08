"""Offline A06/A07 API checks, no network access or persisted side effects."""
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness_capabilities import FixedTaskContext, build_harness, inspect_harness
from agent_framework.openai import OpenAIChatClient


class ContextStub:
    def __init__(self):
        self.instructions = []

    def extend_instructions(self, source_id, value):
        self.instructions.append((source_id, value))


class PublicHarnessTests(unittest.IsolatedAsyncioTestCase):
    async def test_context_provider_hook_contract(self):
        provider = FixedTaskContext("trusted external fact")
        context = ContextStub()
        state = {}
        await provider.before_run(agent=None, session=None, context=context, state=state)
        await provider.after_run(agent=None, session=None, context=context, state=state)
        self.assertEqual(context.instructions, [("poc-task-context", "trusted external fact")])
        self.assertEqual(state, {"before_count": 1, "after_count": 1})

    async def test_factory_installs_public_providers_without_unsafe_defaults(self):
        previous = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = "ci-no-network-placeholder"
        try:
            agent = build_harness(OpenAIChatClient(model="ci-model"))
            result = inspect_harness(agent)
        finally:
            if previous is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = previous
        self.assertTrue(result["native_todo"])
        self.assertTrue(result["native_mode"])
        self.assertTrue(result["custom_context"])
        self.assertTrue(result["file_memory_disabled"])
        self.assertTrue(result["session_serializable"])
        self.assertFalse(result["durable_session_verified"])
        self.assertFalse(result["plan_domain_mapping_verified"])


if __name__ == "__main__":
    unittest.main()
