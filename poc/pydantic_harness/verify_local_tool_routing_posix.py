"""Real Coder read/write/shell tools, one shared Agent, two POSIX workspaces.

Offline FunctionModel responses are deterministic, with no LLM or E2B API.
This POSIX workspace test is a behavior contrast, NOT a CubeSandbox test.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import tempfile

from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelResponse, TextPart, ToolCallPart, ToolReturnPart, UserPromptPart,
)
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.workspaces import LocalWorkspaceBackend
from pydantic_ai_harness.coder import Coder


def scripted_model(messages, info):
    names = {tool.name for tool in info.function_tools}
    assert {"write_file", "read_file", "shell"} <= names
    prompts = [
        str(part.content)
        for message in messages
        for part in message.parts
        if isinstance(part, UserPromptPart)
    ]
    assert prompts
    identity = "alpha" if "alpha" in prompts[0] else "beta"
    tool_results = [
        part
        for message in messages
        for part in message.parts
        if isinstance(part, ToolReturnPart)
    ]
    if len(tool_results) == 0:
        return ModelResponse(parts=[
            ToolCallPart("write_file", {"path": "proof.txt", "content": identity})
        ])
    if len(tool_results) == 1:
        return ModelResponse(parts=[ToolCallPart("read_file", {"path": "proof.txt"})])
    if len(tool_results) == 2:
        return ModelResponse(parts=[
            ToolCallPart("shell", {"command": "cat proof.txt", "timeout": 10})
        ])
    assert len(tool_results) == 3, len(tool_results)
    return ModelResponse(parts=[TextPart("done-" + identity)])


async def main():
    if os.name != "posix":
        print(json.dumps({"outcome": "SKIP", "reason": "LocalWorkspace requires POSIX"}))
        return 2
    with tempfile.TemporaryDirectory(prefix="ahp-pydantic-local-") as root:
        alpha = Path(root) / "alpha"
        beta = Path(root) / "beta"
        alpha.mkdir()
        beta.mkdir()
        # No LocalWorkspace capability is global to the shared agent:
        # each concurrent Run provides its own explicit WorkspaceBackend.
        agent = Agent(
            FunctionModel(scripted_model),
            name="shared-coder-posix",
            capabilities=[Coder(repo_context=False, sub_agents=False)],
        )
        results = await asyncio.gather(
            agent.run("alpha", workspace=LocalWorkspaceBackend(alpha)),
            agent.run("beta", workspace=LocalWorkspaceBackend(beta)),
        )
        assert results[0].output == "done-alpha"
        assert results[1].output == "done-beta"
        assert (alpha / "proof.txt").read_text() == "alpha"
        assert (beta / "proof.txt").read_text() == "beta"
        for idx, identity in enumerate(("alpha", "beta")):
            returns = [
                str(part.content)
                for message in results[idx].all_messages()
                for part in message.parts
                if isinstance(part, ToolReturnPart)
            ]
            assert len(returns) == 3, returns
            assert all(identity in item for item in returns), returns
        print(json.dumps({
            "outcome": "PASS",
            "shared_agent_objects": 1,
            "concurrent_runs": 2,
            "workspace_backends": 2,
            "real_tool_calls_per_run": 3,
            "file_write_read_and_shell": "PASS",
            "workspace_content_cross_write": False,
            "model_api_calls": 0,
            "cube_e2b_compatibility": "NOT_TESTED",
        }, sort_keys=True))
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
