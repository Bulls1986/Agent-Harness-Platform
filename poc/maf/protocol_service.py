"""A18/A19/A20/A21: minimal self-hosted MAF Document Workflow protocol proof.

A restricted FIXTURE-ONLY Responses-compatible subset; NOT an OpenAI
Responses API server, model output, SSE live token streaming, IAM gateway, or
production HTTP service. Its only actions run trusted repo-owned document
fixtures through the official MAF Workflow and commit task facts to Postgres.

Client/UI sees only Harness-owned stable IDs and events, never MAF IDs.
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from document_workflow import run_document_case
from bounded_replan import run_bounded_document_replan
from task_ledger import TaskLedger
from workflow_probe import VerificationFact

app = FastAPI(title="MAF POC-A local protocol proof", version="0.1.0")


class FixtureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # No open-ended prompt, URL, file path or arbitrary code reaches this host.
    input: Literal["document:expected", "document:buggy", "document:replan"]
    stream: Literal[False] = False
    model: Literal["poc-maf-workflow-fixture"] = "poc-maf-workflow-fixture"


def _ledger() -> TaskLedger:
    dsn = os.getenv("POC_POSTGRES_DSN", "")
    if not dsn:
        raise HTTPException(status_code=503, detail="Platform PostgreSQL unavailable")
    return TaskLedger(dsn)


def _event(row: dict, run_id: str) -> dict:
    """Map persisted Harness DB events, preserving order and correlation."""
    payload = row["payload"]
    if row["event_type"] not in ("run.started", "run.terminal", "verification.failed", "plan.replanned"):
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
    return {
        "id": run["run_id"],
        "object": "response",
        "status": ("completed" if run["state"] == "COMPLETED"
                   else "failed" if run["state"] == "FAILED"
                   else "in_progress"),
        "model": "poc-maf-workflow-fixture",
        # No LLM-generated text was produced: don't synthesize assistant output.
        "output": [],
        "error": ({"code": "verification_failure"}
                  if run["state"] == "FAILED" else None),
        "harness": {
            "run_id": run["run_id"],
            "state": run["state"],
            "verification": terminal["payload"].get("verification") if terminal else None,
            "evidence_ref": terminal["payload"].get("evidence_ref") if terminal else None,
            "event_cursor": record["events"][-1]["seq"],
            "fixture_only": True,
            "real_model_invoked": False,
        },
    }


@app.get("/health")
def health():
    return {"status": "ready", "fixture_only": True}


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
async def replay_events(run_id: str, after: int = Query(default=0, ge=0)):
    ledger = _ledger()
    try:
        record = await asyncio.to_thread(ledger.read, run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown Run")
    # Immutable persisted events, no in-memory SSE cursor and no fabricated
    # intermediate Tool/Plan/Approval events.
    items = [_event(row, run_id) for row in record["events"] if row["seq"] > after]

    async def replay():
        for event in items:
            yield (f"id: {event['id']}\n"
                   f"event: {event['type']}\n"
                   f"data: {json.dumps(event, separators=(',', ':'), ensure_ascii=False)}\n\n")

    return StreamingResponse(replay(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})
