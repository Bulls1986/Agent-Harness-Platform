"""No-model SDK public function-tool invocation against live Docker sandbox."""

import asyncio
import json

from unified_sandbox_contract import DockerSandboxProvider, ExecutionBinding


async def main():
    try:
        from agents import FunctionTool
        from agents.tool_context import ToolContext
        from openai_agents_adapter import sandbox_tools
    except ImportError:
        print(json.dumps({"outcome": "SKIP", "reason": "openai-agents not installed"}))
        return 2

    provider = DockerSandboxProvider()
    binding = ExecutionBinding("sdk-run-A", "sdk-scope-A")
    lease = provider.create(binding)
    try:
        tools = sandbox_tools(provider, binding, lease)
        assert len(tools) == 3 and all(isinstance(t, FunctionTool) for t in tools)
        by_name = {t.name: t for t in tools}
        # Public FunctionTool.on_invoke_tool is the callback the SDK runner uses.
        # A minimal public ToolContext exercises the actual SDK schema/parser.
        # No model request or agent Runner is started for this fixture.
        async def call(tool_name: str, args: dict):
            arguments = json.dumps(args)
            context = ToolContext(
                context={}, tool_name=tool_name,
                tool_call_id="call-sandbox-smoke",
                tool_arguments=arguments,
            )
            return await by_name[tool_name].on_invoke_tool(context, arguments)

        await call("sandbox_write", {"name": "proof.txt", "content": "sdk-wrote"})
        observed = await call("sandbox_read", {"name": "proof.txt"})
        shell = await call("sandbox_shell", {"command": "cat proof.txt; id -u"})
        assert observed == "sdk-wrote"
        assert "sdk-wrote" in shell and "10001" in shell, shell
        print(json.dumps({
            "outcome": "PASS", "sdk_public_function_tools": 3,
            "actual_sandbox_exec": True, "host_shell_used": False,
            "model_calls": 0, "sandbox_instances": 1,
            "runner_agent_loop": "NOT_TESTED",
        }, sort_keys=True))
        return 0
    finally:
        provider.close(lease, binding)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))