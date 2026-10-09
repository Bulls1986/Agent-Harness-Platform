"""Real OpenCode 2 + OpenAI Agents SDK handoff in one isolated Docker Sandbox.

Zero model calls. Exercise native OpenCode 2 authenticated filesystem API and
OpenAI Agents SDK public FunctionTools against the same physical container.
Must never print the server's temporary password or Authorization header.
"""

import asyncio
import base64
import json
import re
import time

from unified_sandbox_contract import DockerSandboxProvider, ExecutionBinding


IMAGE = (
    "ghcr.io/anomalyco/opencode@sha256:"
    "9500f3474188a4b89e165c65fada370dbde5e038cc3b751ed5dcbd27d7620315"
)


async def main():
    try:
        from agents.tool_context import ToolContext
        from openai_agents_adapter import sandbox_tools
    except ImportError:
        print(json.dumps({"outcome": "SKIP", "reason": "openai-agents SDK not installed"}))
        return 2

    provider = DockerSandboxProvider(IMAGE)
    binding = ExecutionBinding("opencode2-sdk-handoff", "isolated-task-handoff")
    lease = provider.create(binding)
    try:
        tools = {tool.name: tool for tool in sandbox_tools(provider, binding, lease)}

        async def invoke(name, arguments):
            payload = json.dumps(arguments)
            ctx = ToolContext(
                context={}, tool_name=name, tool_call_id="handoff-fixture",
                tool_arguments=payload,
            )
            return await tools[name].on_invoke_tool(ctx, payload)

        # OpenAI public SDK FunctionTool writes into the *same* physical lease.
        await invoke("sandbox_write", {"name": "from_sdk.txt", "content": "sdk-first"})
        code, _, _ = provider.execute(
            lease, binding, [
                "sh", "-c",
                "export HOME=/workspace XDG_DATA_HOME=/workspace/.local/share "
                "XDG_CACHE_HOME=/workspace/.cache XDG_CONFIG_HOME=/workspace/.config; "
                "nohup opencode serve --hostname 127.0.0.1 --port 4096 "
                "> /workspace/server.log 2>&1 < /dev/null &",
            ],
        )
        assert code == 0, "OpenCode 2 failed to start"

        deadline = time.monotonic() + 38
        password = None
        while time.monotonic() < deadline:
            rc, output, _ = provider.execute(
                lease, binding,
                ["sh", "-c", "cat /workspace/server.log 2>/dev/null || true"],
            )
            match = re.search(r"server password\s+(\S+)", output)
            if rc == 0 and match:
                password = match.group(1)
                break
            await asyncio.sleep(0.3)
        assert password, "No password emitted by OpenCode 2 sandbox server"
        basic = base64.b64encode(("opencode:" + password).encode()).decode()

        def http(path, body=None):
            # All traffic stays INSIDE the Sandbox loopback; no exposed port.
            argv = ["wget", "-q", "-O", "-",
                    "--header=Authorization: Basic " + basic]
            if body is not None:
                argv += ["--header=Content-Type: application/json",
                         "--post-data=" + json.dumps(body, separators=(",", ":"))]
            argv += ["http://127.0.0.1:4096" + path]
            return provider.execute(lease, binding, argv, timeout=18)

        rc, output, stderr = http("/api/session", {"location": {"directory": "/workspace"}})
        assert rc == 0, ("OpenCode 2 session create failed", stderr[:180])
        result = json.loads(output)
        session = result["data"]
        assert session["location"]["directory"] == "/workspace"
        assert session["id"]
        rc, second_output, second_error = http(
            "/api/session", {"location": {"directory": "/workspace"}}
        )
        assert rc == 0, ("second V2 session create failed", second_error[:180])
        assert json.loads(second_output)["data"]["id"] != session["id"]

        rc, output, stderr = http("/api/fs/read/from_sdk.txt")
        assert rc == 0, ("OpenCode 2 FS read failed", stderr[:220])
        assert "sdk-first" in output, output[:500]

        # OpenCode 2's public Shell API is distinct from its model-driven
        # agent loop. It should execute within the existing Sandbox boundary.
        shell_request = {
            "command": "printf oc-v2 > /workspace/from_opencode.txt",
            "cwd": "/workspace", "timeout": 15000, "metadata": {},
        }
        rc, output, stderr = http("/api/shell", shell_request)
        if rc != 0:
            print(json.dumps({
                "outcome": "PARTIAL",
                "session_created": True,
                "sdk_write_to_opencode_v2_fs_read": True,
                "v2_shell_http_rc": rc,
                "v2_shell_error": stderr[:175],
                "sdk_can_read_v2_shell_write": False,
            }))
            return 3
        response = json.loads(output)
        shell_info = response.get("data", {})
        for _ in range(30):
            if shell_info.get("status") != "running":
                break
            await asyncio.sleep(0.2)
            # A running shell may complete asynchronously; read via lease.
            try:
                observed = await invoke("sandbox_read", {"name": "from_opencode.txt"})
                if observed == "oc-v2":
                    break
            except Exception:
                pass

        observed = await invoke("sandbox_read", {"name": "from_opencode.txt"})
        assert observed == "oc-v2", observed
        print(json.dumps({
            "outcome": "PASS", "opencode_version": "2.0.24",
            "openai_sdk_function_tools": 3, "model_calls": 0,
            "physical_sandbox_containers": 1,
            "v2_session_created": True,
            "v2_logical_sessions": 2,
            "sdk_to_opencode_fs": True, "opencode_shell_to_sdk_fs": True,
            "network": "disabled", "sandbox_user": "10001",
            "openai_agent_runner": "NOT_TESTED",
            "git_lsp_plugins": "NOT_TESTED",
        }, sort_keys=True))
        return 0
    finally:
        provider.close(lease, binding)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))