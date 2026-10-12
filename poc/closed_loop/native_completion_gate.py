"""Read-only bounded terminal-status synchronization for pure Hatchet Replan.

Hatchet can publish a finished task result shortly before get_status reports
the workflow terminal. Never promote on a task result alone, a string literal,
or any cancellation acknowledgement. The domain gate MUST recheck independently.
"""
from __future__ import annotations

from enum import Enum
import time
from typing import Callable

from poc.closed_loop.facts import UnsafeDispatch


def await_native_completed(
    lookup_status: Callable[[str], Enum],
    provider_workflow_id: str,
    *,
    timeout_secs: float = 30,
    poll_interval_secs: float = 0.25,
) -> Enum:
    if not provider_workflow_id or timeout_secs <= 0 or poll_interval_secs <= 0:
        raise ValueError("Provider ID and positive bounded timing required")
    deadline = time.monotonic() + timeout_secs
    while True:
        try:
            state = lookup_status(provider_workflow_id)
        except Exception:
            raise UnsafeDispatch("Trusted native status lookup failed; Replan blocked") from None
        if not isinstance(state, Enum) or not isinstance(state.value, str):
            raise UnsafeDispatch("Untyped Provider completion is not authoritative")
        if state.value == "COMPLETED":
            return state
        if state.value in ("FAILED", "CANCELLED", "CANCELED", "TIMED_OUT"):
            raise UnsafeDispatch("Prior Provider ended without verified completion")
        if time.monotonic() >= deadline:
            raise UnsafeDispatch("Provider terminal completion not observed before deadline")
        time.sleep(min(poll_interval_secs, max(.0, deadline - time.monotonic())))
