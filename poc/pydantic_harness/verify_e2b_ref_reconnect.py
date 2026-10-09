"""Offline E2B SDK contract: existing Session WorkspaceRef reconnects, never creates.

Mocks only the public E2B SDK boundary. Does not claim Cube connectivity, file
operations, lifecycle recovery, or real service behavior.
"""

from __future__ import annotations

import asyncio
import importlib.metadata
import json
from types import SimpleNamespace
from unittest.mock import patch

from e2b import AsyncSandbox
from pydantic_ai.workspaces import WorkspaceRef
from pydantic_ai_harness.e2b_sandbox import E2BSandboxBackend


async def main():
    existing = ("session-A-sandbox", "session-B-sandbox")
    connects: list[tuple[str, int | None]] = []
    handles = {
        sandbox_id: SimpleNamespace(sandbox_id=sandbox_id)
        for sandbox_id in existing
    }

    async def sdk_connect(sandbox_id: str, *, timeout: int | None = None, **_):
        connects.append((sandbox_id, timeout))
        await asyncio.sleep(0)
        if sandbox_id not in handles:
            raise RuntimeError("unavailable sandbox")
        return handles[sandbox_id]

    with (
        patch.object(
            AsyncSandbox, "create",
            side_effect=AssertionError("existing Session unexpectedly created new E2B sandbox"),
        ) as create,
        patch.object(AsyncSandbox, "connect", side_effect=sdk_connect) as connect,
    ):
        backends = [
            E2BSandboxBackend(
                ref=WorkspaceRef(provider="e2b", id=sandbox_id),
                sandbox_timeout=180,
            )
            for sandbox_id in existing
        ]

        # Concurrent callers of the SAME Session must acquire a single
        # connection; separate sessions must not receive each other's handle.
        results = await asyncio.gather(
            *(backend.get_sandbox() for backend in backends for _ in range(5))
        )
        assert all(result is handles[existing[0]] for result in results[:5])
        assert all(result is handles[existing[1]] for result in results[5:])
        assert sorted(connects) == [(existing[0], 180), (existing[1], 180)]

        # The backend reuses the acquired handle instead of repeatedly
        # reconnecting on each tool call.
        assert await backends[0].get_sandbox() is handles[existing[0]]
        assert await backends[1].get_sandbox() is handles[existing[1]]
        assert connect.call_count == 2
        assert create.call_count == 0

        # A stale/released Session binding must not provision an empty new
        # workspace behind the caller's back.
        stale = E2BSandboxBackend(
            ref=WorkspaceRef(provider="e2b", id="missing-sandbox"),
            sandbox_timeout=180,
        )
        try:
            await stale.get_sandbox()
        except Exception:
            pass
        else:
            raise AssertionError("missing Sandbox ID unexpectedly resolved")
        assert create.call_count == 0
        assert connect.call_count == 3

    print(json.dumps({
        "outcome": "PASS",
        "harness_version": importlib.metadata.version("pydantic-ai-harness"),
        "e2b_version": importlib.metadata.version("e2b"),
        "separate_session_refs": 2,
        "concurrent_acquisition_callers": 10,
        "sdk_connect_calls_for_two_existing_refs": 2,
        "sdk_create_calls": 0,
        "missing_ref_does_not_recreate_sandbox": True,
        "cube_e2b_live": "NOT_TESTED",
        "sdk_boundary": "MOCKED",
    }, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())