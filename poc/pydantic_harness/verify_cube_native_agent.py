"""LIVE POC: real Pydantic AI Agent tool loop -> Cube native SDK MicroVM.

One Agent instance handles two logical Runs on the SAME approved Sandbox.
This exercises a public tool adapter, not Pydantic E2BSandbox native backend
or OpenCode. FunctionModel makes zero hosted model calls.
"""
from __future__ import annotations
import argparse
import asyncio
from dataclasses import dataclass
import json
import os
from typing import Any
from urllib.request import urlopen

# Pydantic get_type_hints() resolves tool annotations in the module globals.
# Import lazily/optionally so --offline works without Pydantic installed.
try:
    from pydantic_ai import RunContext
except ImportError:
    RunContext = None

@dataclass
class ApprovedBinding:
    session_id: str
    isolation_scope: str
    sandbox: Any

PATH = "/tmp/ahp-pydantic-agent-proof.txt"

def emit(**kw):
    print(json.dumps(kw, ensure_ascii=False, sort_keys=True), flush=True)

def live():
    from cubesandbox import Sandbox
    from pydantic_ai import Agent
    from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart, UserPromptPart
    from pydantic_ai.models.function import FunctionModel

    def fake_model(messages, info):
        assert {"cube_write", "cube_read", "cube_shell"} <= {t.name for t in info.function_tools}
        prompts = [str(p.content) for m in messages for p in m.parts if isinstance(p, UserPromptPart)]
        identity = "alpha" if "alpha" in prompts[0] else "beta"
        results = [p for m in messages for p in m.parts if isinstance(p, ToolReturnPart)]
        if len(results) == 0:
            return ModelResponse(parts=[ToolCallPart("cube_write", {"content": identity})])
        if len(results) == 1:
            return ModelResponse(parts=[ToolCallPart("cube_read", {})])
        if len(results) == 2:
            return ModelResponse(parts=[ToolCallPart("cube_shell", {})])
        assert len(results) == 3, len(results)
        assert identity in str(results[1].content) and identity in str(results[2].content)
        return ModelResponse(parts=[TextPart("done-" + identity)])

    agent = Agent(FunctionModel(fake_model), name="cube-native-agent", deps_type=ApprovedBinding)

    @agent.tool
    def cube_write(ctx: RunContext[ApprovedBinding], content: str) -> str:
        """Write content into the already approved Cube Sandbox lease."""
        assert ctx.deps.isolation_scope == "approved-scope"
        ctx.deps.sandbox.files.write(PATH, content)
        return "written"

    @agent.tool
    def cube_read(ctx: RunContext[ApprovedBinding]) -> str:
        """Read a file from the approved Cube Sandbox lease."""
        assert ctx.deps.isolation_scope == "approved-scope"
        return ctx.deps.sandbox.files.read(PATH)

    @agent.tool
    def cube_shell(ctx: RunContext[ApprovedBinding]) -> str:
        """Execute an innocuous read command in the approved Cube Sandbox lease."""
        assert ctx.deps.isolation_scope == "approved-scope"
        return ctx.deps.sandbox.commands.run("cat " + PATH).stdout

    sb = None
    try:
        sb = Sandbox.create(template=os.environ["CUBE_TEMPLATE_ID"], timeout=150)
        async def run_agents():
            r1 = await agent.run("alpha", deps=ApprovedBinding("session-A", "approved-scope", sb))
            assert r1.output == "done-alpha"
            r2 = await agent.run("beta", deps=ApprovedBinding("session-B", "approved-scope", sb))
            assert r2.output == "done-beta"
            assert sb.files.read(PATH) == "beta"

            # A second independently maintained SDK consumes the same Cube
            # workspace through its public FunctionTool (not native E2B Client).
            from agents import function_tool
            from agents.tool_context import ToolContext

            @function_tool
            def openai_read() -> str:
                """Read the Cube workspace file through the public OpenAI tool API."""
                return sb.files.read(PATH)

            args = "{}"
            tool_ctx = ToolContext(context={}, tool_name=openai_read.name,
                                   tool_call_id="handoff-cube", tool_arguments=args)
            returned = await openai_read.on_invoke_tool(tool_ctx, args)
            assert returned == "beta"
            emit(outcome="PASS", scope="live_cube_native_public_tool_adapters",
                 pydantic_agent_runs=2, pydantic_tool_calls=6,
                 shared_agent_instances=1, shared_cube_microvms=1,
                 openai_function_tool_handoff="PASS", same_workspace="PASS",
                 pydantic_native_e2b_backend="NOT_TESTED",
                 openai_native_e2b_client="NOT_TESTED",
                 opencode2_cube="NOT_TESTED", hosted_model_calls=0)
        asyncio.run(run_agents())
        return 0
    finally:
        if sb is not None:
            sb.kill()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--live", action="store_true")
    opts = p.parse_args()
    endpoint = os.environ.get("CUBE_API_URL", "")
    template = os.environ.get("CUBE_TEMPLATE_ID", "")
    if not opts.live:
        emit(outcome="PASS", scope="offline_preflight", live_cube="NOT_RUN",
             configured=bool(endpoint and template))
        return 0
    if (os.environ.get("CUBE_NATIVE_LIVE_CONFIRM") != "1" or
        not template or not (endpoint.startswith("http://127.0.0.1:") or
                              endpoint.startswith("http://localhost:") or
                              endpoint.startswith("https://"))):
        emit(outcome="BLOCKED", reason="trusted Cube endpoint / template / confirmation required")
        return 2
    try:
        if endpoint.startswith("http://"):
            for port, path in ((3000, "/health"), (8090, "/health"), (9091, "/admin/v1/health")):
                with urlopen("http://127.0.0.1:" + str(port) + path, timeout=3) as response:
                    assert response.status == 200
        return live()
    except Exception as e:
        # Never print user secrets, request headers or SDK exception bodies.
        emit(outcome="FAIL", failed_type=type(e).__name__)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
