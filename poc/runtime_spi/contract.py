"""Platform-owned AgentRuntime SPI *POC*.

No DB, scheduler, IAM or Sandbox infrastructure is created here. The binding
uses accepted platform Execution fencing semantics, not SDK-owned session ids.
Events are normalized but not a replacement for durable Task Facts/Receipts.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
from typing import Awaitable, Callable, Protocol

EXEC_CAPS = frozenset({"shell", "files", "git"})
EVENTS = frozenset({
    "run.started", "response.output_text.delta", "runtime.session.created",
    "tool.call", "tool.result", "run.completed", "run.cancelled",
    "run.failed", "run.unsupported",
})


class RuntimeAdmissionDenied(Exception):
    pass


class UnsupportedRuntimeOperation(Exception):
    pass


@dataclass(frozen=True)
class ExecutionContext:
    run_id: str
    turn_id: str
    session_id: str
    isolation_scope: str
    execution_id: str
    owner_id: str
    fencing_token: int
    workspace_ref: str | None = None

    def __post_init__(self):
        if not all((self.run_id, self.turn_id, self.session_id,
                    self.isolation_scope, self.execution_id, self.owner_id)):
            raise RuntimeAdmissionDenied("Incomplete platform Execution binding")
        if self.fencing_token < 1:
            raise RuntimeAdmissionDenied("Invalid Execution fencing token")


@dataclass(frozen=True)
class SandboxGrant:
    """Attestation from an *external* trusted platform SandboxProvider.

    Sandbox IDs/Session IDs alone are NOT access grants.
    """
    sandbox_id: str
    isolation_scope: str
    execution_id: str
    owner_id: str
    fencing_token: int
    lease_id: str
    capabilities: frozenset[str]


@dataclass(frozen=True)
class RunRequest:
    context: ExecutionContext
    runtime: str
    prompt: str
    operation: str = "model.run"
    capabilities: frozenset[str] = frozenset({"model"})
    sandbox: SandboxGrant | None = None


@dataclass(frozen=True)
class TypedEvent:
    run_id: str
    seq: int
    type: str
    runtime: str
    data: dict[str, str] = field(default_factory=dict)

    def as_sse(self) -> str:
        """Single event string. Transport owns actual SSE socket/backpressure."""
        return ("id: " + self.run_id + ":" + str(self.seq) + "\n"
                + "event: " + self.type + "\n"
                + "data: " + json.dumps(
                    {"run_id": self.run_id, "seq": self.seq,
                     "runtime": self.runtime, **self.data}, sort_keys=True) + "\n\n")


class CancelSignal:
    def __init__(self):
        self._event = asyncio.Event()

    def cancel(self):
        self._event.set()

    @property
    def cancelled(self):
        return self._event.is_set()

    async def wait(self):
        await self._event.wait()


Emit = Callable[[str, dict[str, str]], None]


class AgentRuntimeAdapter(Protocol):
    name: str
    operations: frozenset[str]

    async def invoke(self, request: RunRequest, emit: Emit,
                     cancellation: CancelSignal) -> str:
        ...


class AgentRuntimeDispatcher:
    """Run-level admission and event translation. Not a durable state store.

    A cancellation request always means execution/side effects UNKNOWN until
    the external Executor+Receipt reconciler resolves it; no success receipt is
    inferred from this in-memory cancellation event.
    """

    def __init__(self, *adapters: AgentRuntimeAdapter):
        self._adapters = {a.name: a for a in adapters}
        if len(self._adapters) != len(adapters):
            raise RuntimeAdmissionDenied("Duplicate runtime adapter registration")

    @staticmethod
    def _authorize(request: RunRequest) -> None:
        if not request.runtime or not request.operation or not request.prompt:
            raise RuntimeAdmissionDenied("Missing runtime operation or prompt")
        needed = request.capabilities & EXEC_CAPS
        grant = request.sandbox
        if needed and grant is None:
            raise RuntimeAdmissionDenied("Execution capability requires sandbox grant")
        if grant is not None:
            ctx = request.context
            if not all((grant.sandbox_id, grant.lease_id)) or (
                ctx.isolation_scope != grant.isolation_scope
                or ctx.execution_id != grant.execution_id
                or ctx.owner_id != grant.owner_id
                or ctx.fencing_token != grant.fencing_token
                or not request.capabilities.issubset(grant.capabilities | {"model"})
            ):
                raise RuntimeAdmissionDenied("Stale or cross-scope SandboxGrant")

    async def execute(self, request: RunRequest, *,
                      cancellation: CancelSignal | None = None) -> list[TypedEvent]:
        self._authorize(request)
        adapter = self._adapters.get(request.runtime)
        if adapter is None:
            raise RuntimeAdmissionDenied("Unregistered AgentRuntime Adapter")
        events: list[TypedEvent] = []

        def emit(kind: str, payload: dict[str, str]) -> None:
            if kind not in EVENTS or kind.startswith("run."):
                raise RuntimeAdmissionDenied("Adapter emitted untrusted terminal event")
            if any(not isinstance(x, str) or not isinstance(v, str)
                   for x, v in payload.items()):
                raise RuntimeAdmissionDenied("Typed event payload must be string map")
            events.append(TypedEvent(request.context.run_id, len(events) + 1,
                                     kind, adapter.name, payload))

        def state(kind: str, data: dict[str, str] | None = None):
            events.append(TypedEvent(request.context.run_id, len(events) + 1,
                                     kind, adapter.name, data or {}))

        cancel = cancellation or CancelSignal()
        state("run.started")
        if request.operation not in adapter.operations:
            state("run.unsupported", {"operation": request.operation})
            return events
        if cancel.cancelled:
            state("run.cancelled", {"side_effects": "UNKNOWN"})
            return events
        work = asyncio.create_task(adapter.invoke(request, emit, cancel))
        cancelled = asyncio.create_task(cancel.wait())
        try:
            done, _ = await asyncio.wait({work, cancelled},
                                         return_when=asyncio.FIRST_COMPLETED)
            if cancelled in done and not work.done():
                work.cancel()
                try:
                    await work
                except asyncio.CancelledError:
                    pass
                state("run.cancelled", {"side_effects": "UNKNOWN"})
            else:
                output = await work
                if cancel.cancelled:
                    state("run.cancelled", {"side_effects": "UNKNOWN"})
                else:
                    state("run.completed", {"result": output})
        except UnsupportedRuntimeOperation:
            state("run.unsupported", {"operation": request.operation})
        except Exception as exc:
            state("run.failed", {"error_type": type(exc).__name__})
        finally:
            cancelled.cancel()
        return events
