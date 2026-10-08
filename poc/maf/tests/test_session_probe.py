"""Credential-free proof that A05 requires continuity, not just two text chunks."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import session_probe

class FakeContinuousAgent:
    def create_session(self):
        return {"remembered": None}
    async def run(self, prompt, *, session, stream):
        if "Remember this marker" in prompt:
            session["remembered"] = prompt.split("Remember this marker for the next turn: ", 1)[1].split(".",1)[0]
            yield type("Chunk", (), {"text": "ACK"})()
        else:
            yield type("Chunk", (), {"text": session["remembered"]})()

class FakeStatelessAgent(FakeContinuousAgent):
    async def run(self, prompt, *, session, stream):
        yield type("Chunk", (), {"text": "ACK" if "Remember" in prompt else "I do not know"})()

class SessionProbeTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_continuity_passes(self):
        result = await session_probe.probe_agent(FakeContinuousAgent(), "MAF_POC_123")
        self.assertTrue(session_probe.probe_status(result))
    async def test_stateless_output_fails(self):
        result = await session_probe.probe_agent(FakeStatelessAgent(), "MAF_POC_123")
        self.assertTrue(result["streamed_both_turns"])
        self.assertFalse(session_probe.probe_status(result))
if __name__ == "__main__":
    unittest.main()
