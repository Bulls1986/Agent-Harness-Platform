"""POC-A restricted self-hosted MAF / Harness protocol adapters.

The original fixture-only /v1/responses endpoint remains unchanged.
The separate /v1/live/responses endpoint bridges real MAF model chunks into
persisted Harness typed events and SSE. Neither route is a complete Responses
API implementation or an enterprise IAM / model admission gateway. Host on
trusted loopback only. Clients see platform IDs, not native MAF identifiers.
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from document_workflow import run_document_case
from bounded_replan import run_bounded_document_replan
from task_ledger import TaskLedger
from workflow_probe import VerificationFact
from live_model_protocol import LiveModelLedger, persisted_model_events

app = FastAPI(title="MAF POC-A local protocol proof", version="0.1.0")


class FixtureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # No open-ended prompt, URL, file path or arbitrary code reaches this host.
    input: Literal["document:expected", "document:buggy", "document:replan"]
    stream: Literal[False] = False
    model: Literal["poc-maf-workflow-fixture"] = "poc-maf-workflow-fixture"


class LiveModelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input: str = Field(min_length=1, max_length=2048)
    stream: Literal[True] = True
    model: str | None = None


def _ledger() -> TaskLedger:
    dsn = os.getenv("POC_POSTGRES_DSN", "")
    if not dsn:
        raise HTTPException(status_code=503, detail="Platform PostgreSQL unavailable")
    return TaskLedger(dsn)


def _event(row: dict, run_id: str) -> dict:
    """Map persisted Harness DB events, preserving order and correlation."""
    payload = row["payload"]
    if row["event_type"] not in ("run.started", "run.terminal", "verification.failed", "plan.replanned", "response.output_text.delta"):
        raise ValueError("Unsupported typed event; do not invent protocol metadata")
    return {
        "id": f"{run_id}:{row['seq']}",
        "seq": row["seq"], "run_id": run_id,
        "type": row["event_type"],
        "step_id": payload.get("step_id"),
        "attempt_id": payload.get("attempt_id"),
        "data": payload,
    }


def _response(record: dict) -> dict:
    """Restricted Responses-shaped snapshot, not a streamed model answer."""
    run = record["run"]
    done = run["state"] in ("COMPLETED", "FAILED")
    terminal = next((r for r in record["events"]
                     if r["event_type"] == "run.terminal"), None)
    is_live = run["recipe_version"] == "poc-live-model-v1"
    started = next((r for r in record["events"] if r["event_type"] == "run.started"), None)
    deltas = [r["payload"]["delta"] for r in record["events"]
              if r["event_type"] == "response.output_text.delta"]
    text = "".join(deltas)
    return {
        "id": run["run_id"],
        "object": "response",
        "status": ("completed" if run["state"] == "COMPLETED"
                   else "failed" if run["state"] == "FAILED"
                   else "in_progress"),
        "model": started["payload"].get("model") if is_live and started
                 else "poc-maf-workflow-fixture",
        # Text derives exclusively from durable model deltas; no invented output.
        "output": ([{"type": "message", "role": "assistant",
                     "content": [{"type": "output_text", "text": text}]}]
                   if is_live and text else []),
        "error": ({"code": terminal["payload"].get("failure_type", "verification_failure")}
                  if run["state"] == "FAILED" and terminal else None),
        "harness": {
            "run_id": run["run_id"],
            "state": run["state"],
            "verification": terminal["payload"].get("verification") if terminal else None,
            "evidence_ref": terminal["payload"].get("evidence_ref") if terminal else None,
            "event_cursor": record["events"][-1]["seq"],
            "fixture_only": not is_live,
            "real_model_invoked": bool(deltas) if is_live else False,
        },
    }


def _sse(event: dict) -> str:
    return (f"id: {event['id']}\n"
            f"event: {event['type']}\n"
            f"data: {json.dumps(event, separators=(',', ':'), ensure_ascii=False)}\n\n")


@app.get("/health")
def health():
    return {"status": "ready", "fixture_only": True,
            "live_provider_configured": bool(os.getenv("POC_LITELLM_API_KEY") and
                                             os.getenv("POC_LITELLM_BASE_URL") and
                                             os.getenv("POC_LITELLM_MODEL"))}


@app.post("/v1/live/responses")
async def create_live_response(body: LiveModelRequest, request: Request):
    # Model-only local proof; refuse non-loopback transport before DB/model use.
    # 'testclient' exists only for in-process ASGI conformance tests.
    if request.client is None or request.client.host not in ('127.0.0.1', '::1', 'testclient'):
        raise HTTPException(status_code=403, detail='Local-only model POC endpoint')
    model = os.getenv("POC_LITELLM_MODEL", "")
    base_url = os.getenv("POC_LITELLM_BASE_URL", "")
    key = os.getenv("POC_LITELLM_API_KEY", "")
    if not all((model, base_url, key)):
        raise HTTPException(status_code=503, detail="Live provider not configured")
    if body.model is not None and body.model != model:
        raise HTTPException(status_code=422, detail="Model not admitted to this POC")
    ledger = LiveModelLedger(_ledger().dsn)
    try:
        run_id, step_id, attempt_id, execution_id = await asyncio.to_thread(
            ledger.create, model=model
        )
    except Exception:
        raise HTTPException(status_code=503, detail="Platform PostgreSQL unavailable")

    async def stream():
        record = await asyncio.to_thread(ledger.read, run_id)
        yield _sse(_event(record["events"][0], run_id))
        async for row in persisted_model_events(
            ledger, run_id=run_id, step_id=step_id, attempt_id=attempt_id,
            execution_id=execution_id, prompt=body.input, model=model,
            base_url=base_url, api_key=key,
        ):
            yield _sse(_event(row, run_id))

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Harness-Run-Id": run_id})


@app.post("/v1/responses", status_code=201)
async def create_response(body: FixtureRequest):
    ledger = _ledger()
    try:
        if body.input == "document:replan":
            record = await run_bounded_document_replan(ledger)
        else:
            fact = VerificationFact.example(passed=False, evidence_ref=None)
            execution_id = await asyncio.to_thread(ledger.start, fact)
            outcome = await run_document_case(body.input.removeprefix("document:"), fact)
            await asyncio.to_thread(ledger.finish, fact, outcome, execution_id)
            record = await asyncio.to_thread(ledger.read, fact.run_id)
    except Exception:
        # Do not leak SQL credentials/internal data to HTTP clients.
        raise HTTPException(status_code=503, detail="Local POC execution unavailable")
    return _response(record)


@app.get("/v1/responses/{run_id}")
async def get_response(run_id: str):
    ledger = _ledger()
    try:
        return _response(await asyncio.to_thread(ledger.read, run_id))
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown Run")


@app.get("/v1/runs/{run_id}/events")
async def replay_events(run_id: str, after: int | None = Query(default=None, ge=0),
                        last_event_id: str | None = Header(default=None, alias="Last-Event-ID")):
    if last_event_id is not None:
        prefix = f"{run_id}:"
        suffix = last_event_id[len(prefix):] if last_event_id.startswith(prefix) else ""
        if not suffix.isascii() or not suffix.isdecimal() or len(suffix) > 10:
            raise HTTPException(status_code=422, detail="Invalid Last-Event-ID for Run")
        cursor = int(suffix)
        if cursor > 2147483647:  # event seq is PostgreSQL integer
            raise HTTPException(status_code=422, detail="Event cursor out of range")
        if after is not None and after != cursor:
            raise HTTPException(status_code=422, detail="Conflicting event cursors")
    else:
        cursor = after if after is not None else 0
    ledger = _ledger()
    try:
        record = await asyncio.to_thread(ledger.read, run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown Run")
    # Immutable persisted events, no in-memory SSE cursor and no fabricated
    # intermediate Tool/Plan/Approval events.
    items = [_event(row, run_id) for row in record["events"] if row["seq"] > cursor]

    async def replay():
        for event in items:
            yield _sse(event)

    return StreamingResponse(replay(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})
