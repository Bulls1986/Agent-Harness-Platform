"""C10 restricted read-only Harness Responses/Event bridge for Temporal.

Transport from Harness PostgreSQL only; no Temporal Client/History import.
Does not implement POST/model tokens/live tail, tool/approval stream, IAM or
production Responses API. Never expose the native Temporal Workflow ID.
"""
from __future__ import annotations

import json
import os

import psycopg
from psycopg.rows import dict_row

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import StreamingResponse

app=FastAPI(title="POC-C restricted Harness Event Bridge",version="0.1")


def _load(run_id: str) -> dict:
    dsn=os.environ.get("POC_C_PLATFORM_DSN","")
    if not dsn:
        raise HTTPException(503,detail="Harness PostgreSQL not configured")
    try:
        with psycopg.connect(dsn,row_factory=dict_row) as conn:
            # One repeatable read snapshot; never combine stale status/events.
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            run=conn.execute(
                """SELECT r.run_id,r.turn_id,t.conversation_id,r.state,
                          r.runtime_type,r.recipe_version
                   FROM poc_runs r JOIN poc_turns t ON t.turn_id=r.turn_id
                   WHERE r.run_id=%s""",(run_id,)).fetchone()
            if not run or run["runtime_type"]!="temporal":
                raise HTTPException(404,detail="Run not found")
            attempts=conn.execute(
                """SELECT a.attempt_id,a.state AS attempt_state,
                          s.step_id,e.execution_id,e.state AS execution_state,
                          rec.state AS reconciliation_state
                   FROM poc_c_temporal_bindings b
                   JOIN poc_attempts a ON a.attempt_id=b.attempt_id
                   JOIN poc_steps s ON s.step_id=b.step_id
                   JOIN poc_executions e ON e.execution_id=b.execution_id
                   LEFT JOIN poc_reconciliations rec ON rec.execution_id=b.execution_id
                   WHERE b.run_id=%s AND b.attempt_id=a.attempt_id
                         AND e.attempt_id=a.attempt_id AND s.step_id=a.step_id""",
                (run_id,)).fetchall()
            if len(attempts)!=1:
                raise ValueError("Missing or ambiguous persisted Temporal binding")
            events=conn.execute(
                """SELECT event_id,seq,event_type,payload,created_at
                   FROM poc_events WHERE run_id=%s ORDER BY seq""",
                (run_id,)).fetchall()
        if not events or [e["seq"] for e in events]!=list(range(1,len(events)+1)):
            raise ValueError("Missing or noncontiguous platform event history")
        # Only event types *actually* persisted in this slice; do not synthesize
        # native Workflow terminal events or tokens from Temporal data.
        expected_types={"run.started","execution.unknown"}
        if events[0]["event_type"]!="run.started" or any(
            e["event_type"] not in expected_types for e in events
        ):
            raise ValueError("Unsupported platform event type")
        return {"run":run,"execution":attempts[0],"events":events}
    except HTTPException:
        raise
    except (psycopg.Error,ValueError) as exc:
        raise HTTPException(503,detail="Platform facts unavailable or inconsistent") from exc


def _event(record: dict, row: dict) -> dict:
    run=record["run"]
    execution=record["execution"]
    payload=row["payload"]
    # Never serialize raw payload (contains provider-private Native Workflow
    # identifiers). Explicitly allowlist portable Harness fields only.
    allowed=("step_id","attempt_id","execution_id","failure_type",
             "reconciliation_state")
    data={field:payload[field] for field in allowed if field in payload}
    return {
        "event_id":row["event_id"],
        "id":f"{run['run_id']}:{row['seq']}",
        "sequence":row["seq"],
        "conversation_id":run["conversation_id"],
        "turn_id":run["turn_id"],
        "run_id":run["run_id"],
        "item_id":data.get("attempt_id") or run["run_id"],
        "type":row["event_type"],
        "schema_version":"1",
        "timestamp":row["created_at"].isoformat(),
        "step_id":data.get("step_id") or execution["step_id"],
        "attempt_id":data.get("attempt_id") or execution["attempt_id"],
        "data":data,
    }


def _response(record: dict) -> dict:
    run=record["run"]
    execution=record["execution"]
    needs_reconciliation=(execution["reconciliation_state"]=="PENDING" or
                          execution["attempt_state"]=="UNKNOWN" or
                          execution["execution_state"]=="UNKNOWN")
    status=run["state"]
    # Fail closed: a completed Temporal-native Workflow with UNKNOWN Harness
    # outcome does NOT complete platform Run. It must remain in progress and
    # await trusted reconciliation; do not map native closure to response.
    if needs_reconciliation and status in ("COMPLETED","FAILED","CANCELLED","ABORTED"):
        raise HTTPException(503,detail="Inconsistent terminal run and unresolved execution")
    if status=="COMPLETED":
        # C10 deliberately cannot certify success unless trusted Harness
        # terminal fact has been committed.
        events=record["events"]
        if not any(e["event_type"]=="run.terminal" for e in events):
            raise HTTPException(503,detail="Missing platform terminal evidence")
    return {
        "id":run["run_id"],
        "object":"response",
        "status":("completed" if status=="COMPLETED" else
                  "failed" if status in ("FAILED","ABORTED","CANCELLED") else
                  "in_progress"),
        "model":"poc-temporal-fixture",
        "output":[],
        "error":None,
        "harness":{
            "run_id":run["run_id"],
            "state":status,
            "step_id":execution["step_id"],
            "attempt_id":execution["attempt_id"],
            "execution_id":execution["execution_id"],
            "execution_outcome":execution["execution_state"],
            "reconciliation_status":execution["reconciliation_state"],
            "attention_required":needs_reconciliation,
            "event_cursor":record["events"][-1]["seq"],
            "fixture_only":True,
            "real_model_invoked":False,
        },
    }


@app.get("/health")
def health() -> dict:
    # Process readiness, not a claim that the DB is reachable.
    return {"status":"ready","read_only":True,"fixture_only":True}


@app.post("/v1/responses")
def unsupported_create():
    raise HTTPException(501,detail="C10 is a read-only persisted Run bridge; model execution is not supported")


@app.get("/v1/responses/{run_id}")
def get_response(run_id: str) -> dict:
    return _response(_load(run_id))


@app.get("/v1/runs/{run_id}/events")
def events(run_id: str, after: int | None = Query(default=None,ge=0),
           last_event_id: str | None = Header(default=None,alias="Last-Event-ID")):
    start=0 if after is None else after
    if last_event_id:
        prefix=run_id+":"
        if not last_event_id.startswith(prefix):
            raise HTTPException(422,detail="Cursor belongs to a different Run")
        value=last_event_id[len(prefix):]
        if not value.isdecimal():
            raise HTTPException(422,detail="Invalid SSE cursor")
        last=int(value)
        if after is not None and after!=last:
            raise HTTPException(422,detail="Conflicting SSE cursors")
        start=last
    record=_load(run_id)
    events=[_event(record,row) for row in record["events"] if row["seq"]>start]

    async def replay():
        for event in events:
            yield ("id: "+event["id"]+"\n"
                   "event: "+event["type"]+"\n"
                   "data: "+json.dumps(event,ensure_ascii=False,separators=(",",":"))+"\n\n")

    return StreamingResponse(replay(),media_type="text/event-stream",
                             headers={"Cache-Control":"no-cache",
                                      "X-Harness-Event-Cursor":str(record["events"][-1]["seq"])})
