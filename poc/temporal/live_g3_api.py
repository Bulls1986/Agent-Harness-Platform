"""C15 G3 real self-host Responses subset + persisted live Token SSE.

Public only on explicit loopback/dev networks. C10 remains unchanged. No IAM
production access control here. Native workflow ID kept private by allowlist.
"""
from __future__ import annotations
import asyncio
import json
import os
from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from temporalio.client import Client
from live_g3_facts import LiveFacts,QUEUE,TERMINAL
from live_g3_workflow import LiveStreamWorkflow

app=FastAPI(title="POC-C Real Responses Model Stream",version="0.2")

@app.on_event("startup")
def initialize_owned_schema():
    # Only explicit independent Harness schema; NOT Temporal History DB.
    store().initialize()

class Create(BaseModel):
    model:str=Field(min_length=1,max_length=100)
    input:str=Field(min_length=1,max_length=500)
    stream:bool=False

def store():
    key=os.environ.get("POC_C_PLATFORM_DSN","")
    if not key:raise HTTPException(503,detail="Harness PostgreSQL not configured")
    return LiveFacts(key)

def serialize_event(run,row):
    fields=("delta","sha256","chars","state","step_id","attempt_id","execution_id","version")
    data={k:row["payload"][k] for k in fields if k in row["payload"]}
    return {"id":f"{run}:{row['seq']}","sequence":row["seq"],
            "run_id":run,"type":row["event_type"],"data":data,
            "timestamp":row["created_at"].isoformat()}

@app.get("/health")
def health():
    return {"ready":True,"real_model_enabled":os.environ.get("POC_C15_FAKE_MODEL")!="1",
            "scope":"C15 G3 local self-hosted"}

@app.post("/v1/responses",status_code=201)
async def create(body:Create):
    configured=os.environ.get("POC_C_LITELLM_MODEL")
    if body.model!=configured:
        raise HTTPException(422,detail="Model not configured for this self-host POC")
    s=store()
    try:
        run=await asyncio.to_thread(s.prepare,body.input,body.model)
    except ValueError as exc:
        raise HTTPException(422,detail="Invalid bounded input") from exc
    # G2 pending: persisted immutable Workflow ID before start, but ACK loss
    # requires independent reconcile; never blindly issue a second native ID.
    try:
        c=await Client.connect(os.environ.get("POC_C_TEMPORAL_ADDRESS","127.0.0.1:17234"))
        await c.start_workflow(LiveStreamWorkflow.run,run,
                               id=run["native_workflow_id"],task_queue=QUEUE)

        if os.environ.get("POC_C15_INJECT_START_ACK_LOSS")=="1":
            # Fault injected AFTER the native server accepted Workflow Start.
            await asyncio.to_thread(s.mark_start_uncertain,run["run"])
            raise HTTPException(503,detail={"run_id":run["run"],
                          "kind":"START_ACK_UNKNOWN","reconcile_only":True})
        await asyncio.to_thread(s.ack,run["run"],run["native_workflow_id"])
    except HTTPException:
        raise
    except Exception as exc:
        await asyncio.to_thread(s.mark_start_uncertain,run["run"])
        raise HTTPException(503,detail={"run_id":run["run"],
             "kind":"START_ACK_UNKNOWN","reconcile_only":True}) from exc
    if body.stream:
        return await events(run["run"],after=0,last_event_id=None)
    return {"id":run["run"],"object":"response","status":"in_progress",
            "model":body.model,"harness":{"run_id":run["run"]}}

@app.get("/v1/responses/{run_id}")
def get_response(run_id:str):
    try:
        row,events=store().snapshot(run_id)
    except KeyError:
        raise HTTPException(404,detail="Run not found")
    text="".join(e["payload"]["delta"] for e in events
                 if e["event_type"]=="response.output_text.delta")
    return {"id":run_id,"object":"response",
            "status":"completed" if row["state"]=="COMPLETED" else
                     "cancelled" if row["state"]=="CANCELLED" else
                     "failed" if row["state"]=="FAILED" else "in_progress",
            "model":row["model"],
            "output":[{"type":"message","role":"assistant","content":[
                      {"type":"output_text","text":text}]}] if text else [],
            "harness":{"run_id":run_id,"state":row["state"],
                       "step_id":row["step_id"],"attempt_id":row["attempt_id"],
                       "execution_id":row["execution_id"],
                       "start_state":row["start_state"],
                       "last_event_sequence":events[-1]["seq"] if events else 0}}


@app.post("/v1/responses/{run_id}/reconcile-start")
async def reconcile_start(run_id:str):
    """Read-only Native describe via stable, precommitted Workflow ID."""
    s=store()
    try:row,_=await asyncio.to_thread(s.snapshot,run_id)
    except KeyError:raise HTTPException(404,detail="Run not found")
    try:
        client=await Client.connect(os.environ.get("POC_C_TEMPORAL_ADDRESS","127.0.0.1:17234"))
        info=await client.get_workflow_handle(row["native_workflow_id"]).describe()
        if info.id!=row["native_workflow_id"]:
            raise ValueError("Native Start binding mismatch")
    except Exception:
        # Native might be momentarily unreachable. No duplicate start is safe.
        raise HTTPException(409,detail="START_UNKNOWN; native state not verified")
    await asyncio.to_thread(s.ack,run_id,row["native_workflow_id"])
    ref=await asyncio.to_thread(s.recovery_reference,run_id)
    if not ref or ref["runtime_checkpoint_ref"]!="temporal-workflow-id://"+row["native_workflow_id"]:
        raise HTTPException(503,detail="Missing or mismatched RecoveryPoint reference")
    return {"id":run_id,"start_state":"ACKED","native_start_confirmed":True,
            "same_recovery_point_id":ref["recovery_point_id"],
            "new_native_workflow_created":False}

@app.post("/v1/responses/{run_id}/cancel")
async def cancel_response(run_id:str):
    s=store()
    try:
        row,_=await asyncio.to_thread(s.snapshot,run_id)
    except KeyError:
        raise HTTPException(404,detail="Run not found")
    state=await asyncio.to_thread(s.cancel,run_id)
    if state=="CANCELLED":
        try:
            client=await Client.connect(os.environ.get("POC_C_TEMPORAL_ADDRESS","127.0.0.1:17234"))
            await client.get_workflow_handle(row["native_workflow_id"]).cancel()
        except Exception:
            pass
    return {"id":run_id,"status":state.lower()}

def start_seq(run,after,last_id):
    seq=after or 0
    if last_id:
        prefix=run+":"
        if not last_id.startswith(prefix) or not last_id[len(prefix):].isdecimal():
            raise HTTPException(422,detail="SSE cursor invalid/different Run")
        previous=int(last_id[len(prefix):])
        if after is not None and after!=previous:
            raise HTTPException(422,detail="Conflicting SSE cursors")
        seq=previous
    return seq

@app.get("/v1/responses/{run_id}/events")
@app.get("/v1/runs/{run_id}/events")
async def events(run_id:str,after:int|None=Query(default=None,ge=0),
                 last_event_id:str|None=Header(default=None,alias="Last-Event-ID")):
    s=store()
    try:
        await asyncio.to_thread(s.snapshot,run_id)
    except KeyError:
        raise HTTPException(404,detail="Run not found")
    start=start_seq(run_id,after,last_event_id)
    async def tail():
        seq=start
        for _ in range(1500):
            snapshot,rows=await asyncio.to_thread(s.snapshot,run_id,seq,1000)
            for row in rows:
                value=serialize_event(run_id,row)
                yield ("id: "+value["id"]+"\n"+"event: "+value["type"]+"\n"+
                       "data: "+json.dumps(value,separators=(",",":"),ensure_ascii=False)+"\n\n")
                seq=row["seq"]
            if snapshot["state"] in TERMINAL and not rows:
                break
            await asyncio.sleep(.1)
    return StreamingResponse(tail(),media_type="text/event-stream",
                             headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})
