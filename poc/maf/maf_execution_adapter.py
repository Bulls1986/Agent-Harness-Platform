"""A34 narrow MAF Executor -> Harness dispatch admission -> tool adapter probe.

The MAF handler is a public Executor/WorkflowBuilder extension point. The
Harness-owned PostgreSQL ExecutionOwnership record is authoritative: native
Durable RUNNING handler replay does not authorize a second tool dispatch.
No production MCP/tool call or native Instance binding is represented here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, Never

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler

from execution_ownership import ExecutionOwnership, Ownership


@dataclass(frozen=True)
class GuardedToolRequest:
    """Trusted platform input; never assembled from an untrusted tool argument."""

    ownership: Ownership
    tool_input: str


class HarnessGuardedToolExecutor(Executor):
    def __init__(
        self,
        ownership_store: ExecutionOwnership,
        tool_adapter: Callable[[str], Awaitable[str]],
        *,
        id: str = "harness-tool-dispatch",
    ) -> None:
        super().__init__(id=id)
        self._ownership_store = ownership_store
        self._tool_adapter = tool_adapter

    @handler
    async def guard_and_dispatch(
        self, request: GuardedToolRequest, ctx: WorkflowContext[Never, str]
    ) -> None:
        # This committed DB admission MUST occur before entering the tool.
        # If a Worker dies afterward, the admission is still consumed.
        # A replay may fail the Workflow; it must not re-invoke a dangerous tool.
        self._ownership_store.dispatch(request.ownership)
        output = await self._tool_adapter(request.tool_input)
        await ctx.yield_output(output)


def build_guarded_tool_workflow(
    ownership_store: ExecutionOwnership,
    tool_adapter: Callable[[str], Awaitable[str]],
):
    return WorkflowBuilder(
        name="poc-a34-harness-guarded-tool",
        start_executor=HarnessGuardedToolExecutor(ownership_store, tool_adapter),
    ).build()
