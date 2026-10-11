"""Hatchet v1.42.1 / Engine v0.110.5 Provider metadata correlation adapter.

Do NOT assume the native list_runs(additional_metadata=...) filter is applied.
A pinned live test returned unrelated workflows despite this filter.
Enumerate bounded complete pages and verify EVERY returned row's actual
metadata and native workflow ID. Incomplete enumeration fails CLOSED.
No workflow creation/retry is ever performed here.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from poc.closed_loop.facts import UnsafeDispatch
from poc.closed_loop.segment_reconcile import ProviderMatch


class HatchetSegmentLookup:
    def __init__(self, list_runs: Callable[..., list], *,
                 page_size: int = 50, max_pages: int = 20):
        if not callable(list_runs) or page_size < 2 or max_pages < 1:
            raise ValueError("Native list client and bounded pagination required")
        self._list_runs = list_runs
        self._page_size = page_size
        self._max_pages = max_pages

    def find(self, command_key: str, run_id: str, version: int = 2) -> list[ProviderMatch]:
        if not command_key or not run_id or version != 2:
            raise UnsafeDispatch("Missing frozen segment identity")
        expected = {
            "harness_command_key": command_key,
            "harness_run_id": run_id,
            "harness_plan_version": str(version),
        }
        matches = []
        for page in range(self._max_pages):
            try:
                rows = self._list_runs(
                    additional_metadata=expected,
                    only_tasks=False,
                    limit=self._page_size,
                    offset=page * self._page_size,
                )
            except Exception:
                raise UnsafeDispatch("Native Provider listing unavailable") from None
            if not isinstance(rows, list) or len(rows) > self._page_size:
                raise UnsafeDispatch("Invalid native Provider listing response")
            for row in rows:
                actual = getattr(row, "additional_metadata", None)
                if not isinstance(actual, dict):
                    # Filter may be ignored by the pinned backend. Never
                    # assume an unlabeled workflow belongs to the command.
                    continue
                if not all(actual.get(k) == v for k, v in expected.items()):
                    continue
                identity = getattr(getattr(row, "metadata", None), "id", None)
                if not isinstance(identity, str) or not identity:
                    raise UnsafeDispatch("Native matching workflow lacks authoritative ID")
                matches.append(ProviderMatch(
                    workflow_run_id=identity,
                    command_key=actual["harness_command_key"],
                    run_id=actual["harness_run_id"],
                    plan_version=version,
                ))
            if len(rows) < self._page_size:
                return matches
        raise UnsafeDispatch("Native Provider listing incomplete; stay UNKNOWN")
