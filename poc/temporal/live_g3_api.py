"""C15 G3 real self-host Responses subset + persisted live Token SSE.

Public only on explicit loopback/dev networks. C10 remains unchanged. No IAM
production access control here. Native workflow ID kept private by allowlist.
"""
from __future__ import annotations
import asyncio
import json
import os
from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from temporalio.client import Client
from live_g3_facts import LiveFacts,QUEUE
from live_g3_workflow import LiveStreamWorkflow
from platform_typed_feed import TemporalEventFeed, TERMINAL

app=FastAPI(title="POC-C Real Responses Model Stream",version="0.2")

@app.on_event("startup")
def initialize_owned_schema():
    # Only explicit independent Harness schema; NOT Temporal History DB.
    store().initialize()

class Create(BaseModel):
    model:str=Field(min_length=1,max_length=100)
    input:str=Field(min_length=1,max_length=500)
    stream:bool=False
    save_artifact:bool=False  # POC-only optional S3 output; no default side effect

def store():
    key=os.environ.get("POC_C_PLATFORM_DSN","")
    if not key:raise HTTPException(503,detail="Harness PostgreSQL not configured")
    return LiveFacts(key)

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
        if body.save_artifact and not os.environ.get('POC_C11_S3_ENDPOINT'):
            raise HTTPException(503,detail='S3 Artifact Provider not configured')
        run=await asyncio.to_thread(s.prepare,body.input,body.model,body.save_artifact)
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
                       "execution_state":row["execution_state"],
                       "reconciliation_state":row["reconciliation_state"],
                       "attention_required":row["execution_state"]=="UNKNOWN",
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
    """Persist intent before Native RPC. ACK != terminated; never lie."""
    s=store()
    try:
        row,_=await asyncio.to_thread(s.snapshot,run_id)
        state=await asyncio.to_thread(s.request_cancel,run_id)
    except KeyError:
        raise HTTPException(404,detail="Run not found")
    except ValueError as exc:
        raise HTTPException(409,detail="Cancellation requires reconciliation") from exc
    if state!="CANCELLING":
        return {"id":run_id,"status":state.lower(),"already_terminal":True}
    acknowledgement="UNKNOWN"
    try:
        if os.environ.get("POC_C15_INJECT_CANCEL_SIGNAL_LOSS")=="1":
            # Deterministic failure injection, before Native signal dispatch.
            raise ConnectionError("Injected Native cancel signal uncertainty")
        client=await Client.connect(os.environ.get("POC_C_TEMPORAL_ADDRESS","127.0.0.1:17234"))
        await client.get_workflow_handle(row["native_workflow_id"]).cancel()
        # Even an accepted SDK cancel() must NOT finalize Harness Run.
        await asyncio.to_thread(s.note_cancel_ack,run_id)
        acknowledgement="ACKNOWLEDGED"
    except Exception:
        # Native might be unreachable or may have accepted an RPC before an
        # ACK was lost. Never terminalize or duplicate side effects here.
        pass
    return JSONResponse(status_code=202,content={
        "id":run_id,"status":"cancelling",
        "native_cancel":acknowledgement,"confirmation_required":True})

@app.post("/v1/responses/{run_id}/reconcile-cancel")
async def reconcile_cancel(run_id:str):
    """Read-only official Temporal describe of the frozen Native workflow."""
    s=store()
    try:
        row,_=await asyncio.to_thread(s.snapshot,run_id)
    except KeyError:
        raise HTTPException(404,detail="Run not found")
    if row["state"] in TERMINAL:
        return {"id":run_id,"status":row["state"].lower(),
                "already_terminal":True}
    if row["state"]!="CANCELLING":
        raise HTTPException(409,detail="No pending cancellation")
    try:
        client=await Client.connect(os.environ.get("POC_C_TEMPORAL_ADDRESS","127.0.0.1:17234"))
        info=await client.get_workflow_handle(row["native_workflow_id"]).describe()
        if info.id!=row["native_workflow_id"]:
            raise ValueError("Frozen Native Workflow ID mismatch")
    except Exception:
        raise HTTPException(409,detail={"id":run_id,"status":"cancelling",
                                        "native_termination":"UNKNOWN"})
    native_status=info.status.name
    if native_status=="RUNNING":
        return JSONResponse(status_code=202,content={
            "id":run_id,"status":"cancelling","native_termination":"RUNNING"})
    if native_status not in ("CANCELED","TERMINATED","COMPLETED",
                             "FAILED","TIMED_OUT"):
        # CONTINUED_AS_NEW requires following native reference under the
        # platform frozen binding policy; not proven by this POC.
        raise HTTPException(409,detail={"id":run_id,"status":"cancelling",
                                        "native_termination":"UNKNOWN"})
    try:
        final=await asyncio.to_thread(s.finish_cancel,run_id,native_status)
    except ValueError as exc:
        raise HTTPException(409,detail="Cancellation cannot safely finalize") from exc
    return {"id":run_id,"status":final.lower(),
            "native_termination":native_status,"confirmed":True}

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

async def _typed_events(run_id,after,last_event_id,*,c15_only):
    # /v1/responses is restricted to the C15 response-producing Run.
    # /v1/runs is a generic read-only projection of all supported Temporal
    # platform events, including real C11 Artifact and C16 Reconciliation.
    if c15_only:
        try:
            await asyncio.to_thread(store().snapshot,run_id)
        except KeyError:
            raise HTTPException(404,detail="Response Run not found")
    feed=TemporalEventFeed(store().dsn)
    start=start_seq(run_id,after,last_event_id)
    try:
        await asyncio.to_thread(feed.snapshot,run_id,start)
    except KeyError:
        raise HTTPException(404,detail="Run not found")
    except ValueError as exc:
        raise HTTPException(503,detail="Invalid persisted event stream") from exc
    async def tail():
        seq=start
        for _ in range(1500):
            snapshot,rows=await asyncio.to_thread(feed.snapshot,run_id,seq)
            for value in rows:
                yield ("id: "+value["id"]+"\n"+"event: "+value["type"]+"\n"+
                       "data: "+json.dumps(value,separators=(",",":"),ensure_ascii=False)+"\n\n")
                seq=value["sequence"]
            if (snapshot["state"] in TERMINAL or
                    snapshot.get("attention_required")) and not rows:
                break
            await asyncio.sleep(.1)
    return StreamingResponse(tail(),media_type="text/event-stream",
                             headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

@app.get("/v1/responses/{run_id}/events")
async def events(run_id:str,after:int|None=Query(default=None,ge=0),
                 last_event_id:str|None=Header(default=None,alias="Last-Event-ID")):
    return await _typed_events(run_id,after,last_event_id,c15_only=True)

@app.get("/v1/runs/{run_id}/events")
async def run_events(run_id:str,after:int|None=Query(default=None,ge=0),
                     last_event_id:str|None=Header(default=None,alias="Last-Event-ID")):
    return await _typed_events(run_id,after,last_event_id,c15_only=False)