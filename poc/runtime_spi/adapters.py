"""SDK public interface adapters for the platform-owned Runtime SPI.

SDKs are optional until an adapter is constructed. These two model adapters
emit buffered output_text.delta (NOT real token streaming) and intentionally do
not synthesize Tool Receipts or SDK-specific conversation ids as platform ids.
"""
from __future__ import annotations

from .contract import CancelSignal, Emit, RunRequest, UnsupportedRuntimeOperation


class PydanticRuntimeAdapter:
    name = "pydantic"
    operations = frozenset({"model.run"})

    def __init__(self, agent):
        self.agent = agent

    async def invoke(self, request: RunRequest, emit: Emit,
                     cancellation: CancelSignal) -> str:
        if request.capabilities - {"model"}:
            raise UnsupportedRuntimeOperation("Use explicitly bound ToolAdapters for FS")
        result = await self.agent.run(request.prompt)
        text = str(result.output)
        emit("response.output_text.delta", {"delta": text, "mode": "buffered"})
        return text


class OpenAIAgentsRuntimeAdapter:
    name = "openai-agents"
    operations = frozenset({"model.run"})

    def __init__(self, agent):
        self.agent = agent

    async def invoke(self, request: RunRequest, emit: Emit,
                     cancellation: CancelSignal) -> str:
        if request.capabilities - {"model"}:
            raise UnsupportedRuntimeOperation("Use explicitly bound ToolAdapters for FS")
        from agents import Runner
        result = await Runner.run(self.agent, input=request.prompt)
        text = str(result.final_output)
        emit("response.output_text.delta", {"delta": text, "mode": "buffered"})
        return text


class OpenCodeV2SessionAdapter:
    """Limited public V2 API: prepare session in *trusted bound* Sandbox.

    This is NOT a hosted-model prompt run, nor Host-native Tools remoting.
    The caller supplies a trusted async session factory that uses the lease
    binding to select an already-authorized Sandbox-hosted HTTP endpoint.
    """
    name = "opencode2"
    operations = frozenset({"session.prepare"})

    def __init__(self, create_bound_session):
        self.create_bound_session = create_bound_session

    async def invoke(self, request: RunRequest, emit: Emit,
                     cancellation: CancelSignal) -> str:
        if request.sandbox is None:
            raise UnsupportedRuntimeOperation("OpenCode V2 needs a trusted Cube lease")
        native_session_id = await self.create_bound_session(request.context,
                                                            request.sandbox)
        if not isinstance(native_session_id, str) or not native_session_id:
            raise RuntimeError("Invalid OpenCode V2 session response")
        emit("runtime.session.created", {"runtime_session_id": native_session_id})
        return "session.prepared"
