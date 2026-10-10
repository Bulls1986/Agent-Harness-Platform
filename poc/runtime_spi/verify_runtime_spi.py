"""Reproducible AgentRuntime SPI: offline contract and opt-in *real* SDK runs.

--sdk requires installed public Pydantic AI + OpenAI Agents SDK, and runs
their actual Agent.run / Runner.run using deterministic local model doubles.
No network/model costs; DOES NOT imply real LLM Agent loop or token streaming.
"""
import argparse
import asyncio
import json
import pathlib
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from poc.runtime_spi.contract import (
    AgentRuntimeDispatcher, CancelSignal, ExecutionContext, RunRequest,
    RuntimeAdmissionDenied, SandboxGrant,
)
from poc.runtime_spi.adapters import (
    PydanticRuntimeAdapter, OpenAIAgentsRuntimeAdapter, OpenCodeV2SessionAdapter,
)

CONTEXT = ExecutionContext(
    run_id="run-a", turn_id="turn-a", session_id="session-a",
    isolation_scope="trusted-scope-a", execution_id="execution-a",
    owner_id="worker-a", fencing_token=7, workspace_ref="ws-a",
)
GRANT = SandboxGrant(
    sandbox_id="cube-1", lease_id="lease-a",
    isolation_scope=CONTEXT.isolation_scope,
    execution_id=CONTEXT.execution_id,
    owner_id=CONTEXT.owner_id,
    fencing_token=CONTEXT.fencing_token,
    capabilities=frozenset({"shell", "files", "git"}),
)


class ControlledAdapter:
    name = "test-only"
    operations = frozenset({"model.run"})

    def __init__(self, state="pass"):
        self.state = state
        self.invocations = 0

    async def invoke(self, req, emit, cancellation):
        self.invocations += 1
        if self.state == "hold":
            await asyncio.sleep(30)
        elif self.state == "spoof":
            emit("run.completed", {})
        elif self.state == "fail":
            raise ValueError("expected failure; no model invoked")
        emit("response.output_text.delta", {"delta": "ok", "mode": "buffered"})
        return "ok"


async def offline() -> int:
    adapter = ControlledAdapter()
    dispatcher = AgentRuntimeDispatcher(adapter, OpenCodeV2SessionAdapter(
        lambda _ctx, _grant: asyncio.sleep(0, result="native-oc-session")))
    basic = RunRequest(CONTEXT, "test-only", "hello")
    ev = await dispatcher.execute(basic)
    assert [e.type for e in ev] == [
        "run.started", "response.output_text.delta", "run.completed"]
    assert [e.seq for e in ev] == [1, 2, 3]
    assert "event: response.output_text.delta" in ev[1].as_sse()
    assert adapter.invocations == 1  # no sandbox for model-only run

    for grant in (
        None,
        SandboxGrant(**{**GRANT.__dict__, "fencing_token": 6}),
        SandboxGrant(**{**GRANT.__dict__, "isolation_scope": "other"}),
        SandboxGrant(**{**GRANT.__dict__, "owner_id": "other"}),
        SandboxGrant(**{**GRANT.__dict__, "execution_id": "other"}),
        SandboxGrant(**{**GRANT.__dict__, "capabilities": frozenset({"git"})}),
    ):
        req = RunRequest(CONTEXT, "test-only", "a", capabilities=frozenset({"files"}),
                         sandbox=grant)
        try:
            await dispatcher.execute(req)
            raise AssertionError("Cross-scope or unleased FS was not rejected")
        except RuntimeAdmissionDenied:
            pass
    assert adapter.invocations == 1, "Rejected calls must not touch Runtime SDK"

    git_req = RunRequest(CONTEXT, "opencode2", "prepare only",
                         operation="session.prepare",
                         capabilities=frozenset({"files"}), sandbox=GRANT)
    events = await dispatcher.execute(git_req)
    assert [e.type for e in events] == [
        "run.started", "runtime.session.created", "run.completed"]
    assert events[1].data["runtime_session_id"] == "native-oc-session"
    assert (await dispatcher.execute(RunRequest(CONTEXT, "opencode2", "chat")))[-1].type == "run.unsupported"

    cancelled = CancelSignal()
    cancelled.cancel()
    assert (await dispatcher.execute(basic, cancellation=cancelled))[-1].type == "run.cancelled"
    assert adapter.invocations == 1
    sleeping = ControlledAdapter("hold")
    c = CancelSignal()
    work = asyncio.create_task(AgentRuntimeDispatcher(sleeping).execute(
        basic, cancellation=c))
    await asyncio.sleep(0.01)
    c.cancel()
    result = await asyncio.wait_for(work, timeout=2)
    assert result[-1].type == "run.cancelled"
    assert result[-1].data["side_effects"] == "UNKNOWN"

    for state, expected in (("fail", "run.failed"), ("spoof", "run.failed")):
        e = await AgentRuntimeDispatcher(ControlledAdapter(state)).execute(basic)
        assert e[-1].type == expected
    try:
        AgentRuntimeDispatcher(ControlledAdapter(), ControlledAdapter())
        raise AssertionError("duplicate adapter accepted")
    except RuntimeAdmissionDenied:
        pass
    print(json.dumps({"scope":"offline_binding_and_events","outcome":"PASS",
                      "guard_scenarios":6, "no_sandbox_model_run": "PASS",
                      "cancel_unknown_receipt":"PASS", "opencode_session":"MOCK_ONLY",
                      "sdk_runs":"NOT_RUN"},sort_keys=True),flush=True)
    return 0


async def sdk_tests() -> int:
    # Public Pydantic AI SDK Agent.run, not mocking its run method.
    from pydantic_ai import Agent as PydanticAgent
    from pydantic_ai.models.function import FunctionModel
    from pydantic_ai.messages import ModelResponse as PDResponse, TextPart
    def local_function(_messages, _info):
        return PDResponse(parts=[TextPart("pydantic-sdk-real-run")])

    p_adapter = PydanticRuntimeAdapter(PydanticAgent(FunctionModel(local_function)))
    p = await AgentRuntimeDispatcher(p_adapter).execute(
        RunRequest(CONTEXT, "pydantic", "hello"))
    assert p[-1].type == "run.completed"
    assert p[-1].data["result"] == "pydantic-sdk-real-run"

    # Public OpenAI Agents SDK Runner.run with a local deterministic Model,
    # no HTTP API calls, no private SDK patching and no model billing.
    from agents import Agent as OpenAIAgent
    from agents.models.interface import Model, ModelResponse
    from agents.usage import Usage
    from openai.types.responses import ResponseOutputMessage, ResponseOutputText

    class LocalModel(Model):
        async def get_response(self, *args, **kwargs):
            msg = ResponseOutputMessage(
                id="msg-test", role="assistant", type="message",
                content=[ResponseOutputText(
                    annotations=[], text="openai-sdk-real-run", type="output_text")],
                status="completed")
            return ModelResponse(output=[msg], usage=Usage(requests=1), response_id="resp-test")
        async def stream_response(self, *args, **kwargs):
            if False:
                yield None
            raise NotImplementedError("Streaming model not implemented by this fixture")

    o_adapter = OpenAIAgentsRuntimeAdapter(OpenAIAgent(name="local", model=LocalModel()))
    q = await AgentRuntimeDispatcher(o_adapter).execute(
        RunRequest(CONTEXT, "openai-agents", "hello"))
    assert q[-1].type == "run.completed", [(e.type, e.data) for e in q]
    assert q[-1].data["result"] == "openai-sdk-real-run"
    for ev in (p, q):
        assert ev[1].type == "response.output_text.delta"
        assert ev[1].data["mode"] == "buffered"
    print(json.dumps({"scope":"actual_public_agent_sdk_calls",
                      "pydantic_agent_run":"PASS","openai_runner_run":"PASS",
                      "token_streaming":"NOT_TESTED",
                      "hosted_model_calls":0, "opencode_model_loop":"NOT_TESTED",
                      "outcome":"PASS"},sort_keys=True),flush=True)
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sdk", action="store_true")
    args = parser.parse_args()
    async def run():
        await offline()
        if args.sdk:
            await sdk_tests()
    asyncio.run(run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
