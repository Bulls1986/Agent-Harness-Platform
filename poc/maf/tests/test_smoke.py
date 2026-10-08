"""Offline contract tests for the MAF POC-A0 smoke harness."""

import io
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import smoke  # noqa: E402


class FakeAgent:
    def __init__(self):
        self.session = object()
        self.seen = []

    def create_session(self):
        return self.session

    async def run(self, prompt, *, session, stream):
        self.seen.append((prompt, session, stream))
        yield SimpleNamespace(text="first")
        yield SimpleNamespace(text=None)
        yield SimpleNamespace(text=" second")


class EmptyAgent(FakeAgent):
    async def run(self, prompt, *, session, stream):
        self.seen.append((prompt, session, stream))
        yield SimpleNamespace(text=None)


class ConfigTests(unittest.TestCase):
    def test_missing_key_is_error(self):
        with self.assertRaisesRegex(smoke.SmokeConfigurationError, "OPENAI_API_KEY"):
            smoke.resolve_model({"MAF_POC_MODEL": "example"})

    def test_missing_model_is_error(self):
        with self.assertRaisesRegex(smoke.SmokeConfigurationError, "MAF_POC_MODEL"):
            smoke.resolve_model({"OPENAI_API_KEY": "fake"})

    def test_explicit_model_overrides_environment(self):
        self.assertEqual(
            smoke.resolve_model(
                {"OPENAI_API_KEY": "fake", "MAF_POC_MODEL": "old"}, "new"
            ),
            "new",
        )

    def test_blank_model_cannot_pass(self):
        with self.assertRaises(smoke.SmokeConfigurationError):
            smoke.resolve_model({"OPENAI_API_KEY": "fake"}, "   ")


class StreamingTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_turns_reuse_one_session(self):
        agent = FakeAgent()
        out = io.StringIO()
        self.assertEqual(
            await smoke.run_smoke(agent, ("plan", "follow-up"), out),
            (True, True),
        )
        self.assertEqual(out.getvalue(), "first second\nfirst second\n")
        self.assertEqual([record[0] for record in agent.seen], ["plan", "follow-up"])
        for _, session, streaming in agent.seen:
            self.assertIs(session, agent.session)
            self.assertTrue(streaming)

    async def test_empty_text_does_not_claim_pass(self):
        agent = EmptyAgent()
        self.assertEqual(
            await smoke.run_smoke(agent, ("prompt",), io.StringIO()), (False,)
        )


if __name__ == "__main__":
    unittest.main()
