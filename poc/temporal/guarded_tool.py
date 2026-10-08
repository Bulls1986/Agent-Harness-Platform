"""C06 true Temporal Activity retry after process death past external Tool dispatch.

The protected Tool Adapter is a native Temporal Activity, never workflow code.
The first worker is killed AFTER receiving a 200 from an isolated HTTP sink
but BEFORE acknowledging Temporal Activity completion. Temporal will retry
after start_to_close_timeout. Second worker must not call sink again.
"""
from __future__ import annotations

from dataclasses import asdict
import json
import os
import urllib.request

from temporalio import activity
from temporalio.exceptions import ApplicationError

from platform_facts import FrozenTemporal, TemporalTaskFacts, FrozenTemporalMismatch
from execution_ownership import StaleExecutionOwner


@activity.defn(name="c06_pure_retry_probe")
async def pure_retry_probe(request: dict) -> dict:
    """A transient infrastructure failure retries only this PURE Activity."""
    if activity.info().attempt == 1:
        raise ApplicationError("Controlled retry before any effect",type="TRANSIENT_INFRA")
    return {"outcome":"PURE_RECOVERED","activity_attempt":activity.info().attempt}


@activity.defn(name="c06_guarded_nonretryable_tool")
async def guarded_tool(request: dict) -> dict:
    expected=FrozenTemporal(**request["binding"])
    actor=os.environ["POC_C_WORKER_ACTOR"]
    store=TemporalTaskFacts(os.environ["POC_C_PLATFORM_DSN"])
    try:
        store.admit(expected,worker_id=actor)
    except StaleExecutionOwner:
        # The native Temporal retry is NOT an authorized re-dispatch.
        state=store.quarantine_after_dispatch(expected)
        return {"outcome":"UNKNOWN","reconciliation":state,
                "activity_retry_attempt":activity.info().attempt,
                "external_action_dispatched_by_this_retry":False}
    # Any other failure is fatal / fail-closed; do not post external Tool.
    if actor!="worker-A":
        raise FrozenTemporalMismatch("Unexpected new dispatch from a replacement Worker")
    body=json.dumps({"execution_id":expected.execution_id,
                     "attempt_id":expected.attempt_id}).encode()
    req=urllib.request.Request(
        request["tool_url"],data=body,method="POST",
        headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=6) as response:
        if response.status!=200:
            raise RuntimeError("Tool sink did not ACK")
        response.read()
    # Controlled crash after known external receipt, before Temporal Activity
    # completion is committed. Never run this test in an enterprise Worker!
    os._exit(74)
