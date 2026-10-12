"""DEV-M5 1.4: actual Cube provider inventory unchanged for model-only Run.

Uses real Cube SDK + deterministic platform adapter (no model charges).
This proves the Harness dispatcher does not allocate a VM for this path,
NOT 100-concurrent-Run capacity nor OpenCode Guest execution.
"""
from __future__ import annotations

import asyncio
import json
import os

from poc.runtime_spi.contract import AgentRuntimeDispatcher, ExecutionContext, RunRequest


class ModelOnlyProof:
    """Explicit synthetic model port: zero File/Tool/Sandbox capabilities."""

    name = "synthetic-model-only"
    operations = frozenset({"model.run"})

    def __init__(self):
        self.invocations = 0

    async def invoke(self, request, emit, cancellation):
        self.invocations += 1
        emit("response.output_text.delta",
             {"delta": "synthetic-model-only-completed", "mode": "buffered"})
        return "synthetic-model-only-completed"


def _inventory(sdk) -> set[str]:
    rows = sdk.list()
    if not isinstance(rows, list):
        raise RuntimeError("Native Cube listing not reliable")
    result: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("sandboxID"), str):
            raise RuntimeError("Malformed native Cube list: cannot prove zero allocation")
        result.add(row["sandboxID"])
    if len(result) != len(rows):
        raise RuntimeError("Duplicate native Cube locator in listing")
    return result


async def execute_model_only(adapter) -> None:
    ctx = ExecutionContext(
        run_id="m5-zero-sandbox", turn_id="t", session_id="s",
        isolation_scope="synthetic-project", execution_id="e",
        owner_id="worker-model", fencing_token=1,
    )
    events = await AgentRuntimeDispatcher(adapter).execute(RunRequest(
        context=ctx, runtime=adapter.name, prompt="synthetic no-tool result",
        capabilities=frozenset({"model"}), operation="model.run",
        sandbox=None))
    if [evt.type for evt in events] != [
            "run.started", "response.output_text.delta", "run.completed"]:
        raise RuntimeError("Model-only Run did not complete without Sandbox")


def main() -> None:
    if not os.environ.get("CUBE_API_URL"):
        raise RuntimeError("Native Cube endpoint mandatory")
    from cubesandbox import Sandbox
    before = _inventory(Sandbox)
    adapter = ModelOnlyProof()
    asyncio.run(execute_model_only(adapter))
    after = _inventory(Sandbox)
    if before != after or adapter.invocations != 1:
        raise RuntimeError("Model-only executed an unexpected Sandbox effect")
    print(json.dumps({
        "outcome": "PASS_REAL_PROVIDER_ZERO_SANDBOX",
        "native_provider_inventory_unchanged": True,
        "sandbox_allocations": 0,
        "model_only_dispatches": adapter.invocations,
        "existing_sandboxes": len(before),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
