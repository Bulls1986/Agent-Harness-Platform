"""Real Cube E2B API + Pydantic AI Coder tool-chain smoke, opt-in only.

The test provisions one Cube Sandbox with the public AsyncSandbox.create API,
reattaches by WorkspaceRef without provisioning another sandbox, then executes
actual Coder write/read/shell tool calls with a deterministic FunctionModel.
It does not call a hosted model, create persistent volumes or print credentials.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

from e2b import AsyncSandbox
from pydantic_ai import Agent
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.workspaces import WorkspaceRef
from pydantic_ai_harness.coder import Coder
from pydantic_ai_harness.e2b_sandbox import E2BSandbox

from verify_local_tool_routing_posix import scripted_model

# Reuse the approved Cube-specific preflight rather than silently reaching
# the default E2B Cloud endpoint if required Cube configuration is absent.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "opencode_sandbox"))
from verify_cube_e2b import configuration  # noqa: E402


async def run_live(config):
    os.environ["E2B_API_URL"] = config["url"]
    os.environ["E2B_API_KEY"] = config["key"]
    sandbox = None
    try:
        sandbox = await AsyncSandbox.create(template=config["template"], timeout=180)
        ref = WorkspaceRef(provider="e2b", id=sandbox.sandbox_id)
        agent = Agent(
            FunctionModel(scripted_model),
            name="cube-e2b-coder",
            capabilities=[
                E2BSandbox(working_dir="/home/user"),
                Coder(repo_context=False, sub_agents=False),
            ],
        )
        # Any attempt to allocate another Sandbox during the two runs fails.
        with patch.object(
            AsyncSandbox, "create",
            side_effect=AssertionError("Coder attempted to create another sandbox"),
        ):
            first = await agent.run("alpha", workspace=ref)
            second = await agent.run("beta", workspace=ref)
        assert first.output == "done-alpha"
        assert second.output == "done-beta"
        assert "beta" in await sandbox.files.read("/home/user/proof.txt")
        print(json.dumps({
            "outcome": "PASS",
            "provider": "real_cube_e2b",
            "harness_version": importlib.metadata.version("pydantic-ai-harness"),
            "workspace_ref_reused": True,
            "sandbox_instances_created": 1,
            "coder_tool_runs": 2,
            "real_write_read_shell": True,
            "model_api_calls": 0,
            "openai_agents_sdk_same_sandbox_handoff": "NOT_TESTED",
        }, sort_keys=True))
        return 0
    finally:
        if sandbox is not None:
            sandbox.kill()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    cfg, blocked = configuration()
    if not args.live:
        print(json.dumps({
            "outcome": "PASS",
            "scope": "offline_preflight",
            "cube_configured": bool(cfg),
            "live_cube": "NOT_RUN",
            "blocking_reason": blocked,
        }, sort_keys=True))
        return 0
    if blocked:
        print(json.dumps({"outcome": "BLOCKED", "reason": blocked}, sort_keys=True))
        return 2
    if os.environ.get("CUBE_E2B_LIVE_CONFIRM") != "1":
        print(json.dumps({
            "outcome": "BLOCKED", "reason": "set CUBE_E2B_LIVE_CONFIRM=1"
        }, sort_keys=True))
        return 2
    try:
        return asyncio.run(run_live(cfg))
    except Exception as exc:
        # SDK errors may include API URL/token/transport details: never print them.
        print(json.dumps({
            "outcome": "FAIL", "scope": "cube_e2b_live",
            "failed_type": type(exc).__name__,
        }, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
