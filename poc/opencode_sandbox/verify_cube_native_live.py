"""Opt-in real Cube native SDK POC; native Cube != official E2B SDK compatibility."""
from __future__ import annotations

import argparse
import asyncio
import json
import os

def output(**data):
    print(json.dumps(data, sort_keys=True), flush=True)

def check_live(template, openai_bridge):
    from cubesandbox import Sandbox
    sb = None
    try:
        sb = Sandbox.create(template=template, timeout=150)
        path = "/tmp/ahp-cube-native-proof.txt"
        sb.files.write(path, "alpha")
        assert sb.commands.run("cat " + path).stdout.strip() == "alpha"
        new_client = Sandbox.connect(sb.sandbox_id)
        assert new_client.files.read(path) == "alpha"
        new_client.commands.run("printf beta > " + path)
        assert sb.files.read(path) == "beta"

        if openai_bridge:
            from agents import function_tool
            from agents.tool_context import ToolContext

            @function_tool
            async def cube_read(filename: str) -> str:
                return sb.files.read(filename)

            args = json.dumps({"filename": path})
            context = ToolContext(context={}, tool_name=cube_read.name,
                                  tool_call_id="cube-proof", tool_arguments=args)
            assert asyncio.run(cube_read.on_invoke_tool(context, args)) == "beta"

        output(outcome="PASS", provider="Cube native SDK", sandbox_id=sb.sandbox_id,
               real_shell_files="PASS", reconnect_same_sandbox="PASS",
               openai_function_tool="PASS" if openai_bridge else "NOT_RUN",
               official_e2b_sdk="NOT_TESTED", agent_loop="NOT_TESTED",
               sandbox_created=1, model_calls=0)
        return 0
    finally:
        if sb is not None:
            sb.kill()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--openai-function-tool", action="store_true")
    args = parser.parse_args()
    url = os.environ.get("CUBE_API_URL", "")
    template = os.environ.get("CUBE_TEMPLATE_ID", "")
    if not args.live:
        output(outcome="PASS", scope="offline_only", live_cube="NOT_RUN",
               configured=bool(url and template))
        return 0
    if not (url.startswith("http://127.0.0.1:") or url.startswith("http://localhost:") or url.startswith("https://")):
        output(outcome="BLOCKED", reason="local or HTTPS Cube endpoint required")
        return 2
    if not template or os.environ.get("CUBE_NATIVE_LIVE_CONFIRM") != "1":
        output(outcome="BLOCKED", reason="template and explicit confirmation required")
        return 2
    if url.startswith(("http://127.0.0.1:", "http://localhost:")):
        # A Cube API health 200 is not enough: template artifacts require 8090
        # and Cubelet policy pushes require CubeEgress 9091. Fail closed.
        from urllib.request import urlopen
        for port, path in ((3000, "/health"), (8090, "/health"),
                           (9091, "/admin/v1/health")):
            try:
                with urlopen("http://127.0.0.1:" + str(port) + path,
                             timeout=3) as response:
                    if response.status != 200:
                        raise RuntimeError("service not ready")
            except Exception:
                output(outcome="BLOCKED", reason="local Cube dependency unavailable",
                       dependency_port=port)
                return 2
    try:
        return check_live(template, args.openai_function_tool)
    except Exception as exc:
        output(outcome="FAIL", failed_type=type(exc).__name__)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
