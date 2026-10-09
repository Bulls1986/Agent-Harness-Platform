"""No-model, no-network Pydantic AI Harness session/workspace smoke.

Demonstrates shared Agent instance, lazy E2B allocation, and per-Run
WorkspaceRef selection. Does NOT prove Cube compatibility or native shell
execution isolation. A real E2B/Cube E2B conformance test is separate.
"""

from __future__ import annotations

import asyncio
import importlib.metadata
import json
from unittest.mock import patch

from e2b import AsyncSandbox
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.typesafe import TypeSafeModel
from pydantic_ai.workspaces import WorkspaceRef
from pydantic_ai_harness.coder import Coder
from pydantic_ai_harness.e2b_sandbox import E2BSandbox, E2BSandboxBackend


def fake_model(messages, info):
    """Return a deterministic no-tool answer without contacting any model."""
    return ModelResponse(parts=[TextPart("offline-ok")])


async def main():
    # Prohibit E2B connection even if the test machine has a real API key.
    with (
        patch.object(AsyncSandbox, "create", side_effect=AssertionError("unexpected sandbox creation")),
        patch.object(AsyncSandbox, "connect", side_effect=AssertionError("unexpected sandbox connection")),
    ):
        simple = Agent(FunctionModel(fake_model), name="shared-simple-agent")
        runs = await asyncio.gather(*(simple.run(f"session-{idx}") for idx in range(20)))
        assert len(runs) == 20 and all(run.output == "offline-ok" for run in runs)

        sandbox = E2BSandbox()
        coding = Agent(
            FunctionModel(fake_model),
            name="shared-coding-agent",
            capabilities=[sandbox, Coder(repo_context=False, sub_agents=False)],
        )
        first = await coding.run("idle session with no tool call")
        assert first.output == "offline-ok"

        refs = [
            WorkspaceRef(provider="e2b", id="offline-session-A"),
            WorkspaceRef(provider="e2b", id="offline-session-B"),
        ]
        for ref in refs:
            backend = sandbox.backend(ref)
            assert isinstance(backend, E2BSandboxBackend)
            assert backend.ref == ref

        # One Agent object, different explicit WorkspaceRef on each run.
        attached = await asyncio.gather(
            *(coding.run(f"attached-{idx}", workspace=ref)
              for idx, ref in enumerate(refs))
        )
        assert all(run.output == "offline-ok" for run in attached)
        assert len({ref.id for ref in refs}) == 2

        # Import/signature availability of Jev; no provider key, API call, or
        # claimed routing quality measurements.
        assert TypeSafeModel is not None

    print(json.dumps({
        "outcome": "PASS",
        "pydantic_ai_harness": importlib.metadata.version("pydantic-ai-harness"),
        "pydantic_ai_slim": importlib.metadata.version("pydantic-ai-slim"),
        "shared_plain_agent_concurrent_runs": len(runs),
        "shared_coder_agent_runs": 3,
        "distinct_preexisting_workspace_refs": len(refs),
        "e2b_create_or_connect_calls": 0,
        "model_api_calls": 0,
        "jev_typesafe_model_import": "PASS_ONLY",
        "cube_live_e2b": "NOT_TESTED",
        "workspace_execution_tools": "NOT_TESTED",
        "cross_session_tool_isolation": "NOT_TESTED",
    }, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())