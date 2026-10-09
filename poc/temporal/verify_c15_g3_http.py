"""C15 live G3 end-to-end HTTP + Temporal Worker + persisted PG Token SSE.

Only real model mode is evidence for G3 live tokens; offline CI is explicit
fixture and cannot claim real model success.
"""
from __future__ import annotations
import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import httpx

def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        return sock.getsockname()[1]

def stop(p):
    if p and p.poll() is None:
        p.terminate()
        try:p.wait(timeout=7)
        except subprocess.TimeoutExpired:p.kill();p.wait(timeout=7)

async def ready(client,proc):
    for _ in range(95):
        if proc.poll() is not None:raise RuntimeError("G3 HTTP subprocess exited")
        try:
            r=await client.get("/health",timeout=1)
            if r.status_code==200:return
        except (httpx.HTTPError,ValueError):pass
        await asyncio.sleep(.13)
    raise TimeoutError("G3 API never started")

async def exercise():
    fake=os.environ.get("POC_C15_FAKE_MODEL")=="1"
    required=("POC_C_PLATFORM_DSN","POC_C_LITELLM_MODEL")
    if not all(os.environ.get(k) for k in required):raise ValueError("G3 env missing")
    if not fake and not all(os.environ.get(k) for k in
        ("POC_C_LITELLM_BASE_URL","JUSDA_LITELLM_API_KEY")):
        raise ValueError("Real model gateway environment missing")
    env=os.environ.copy()
    env["POC_C_LIVE_PROTOCOL"]="1"
    env["POC_C_TASK_QUEUE"]="poc-c15-g3-v1"
    api_port=port()
    cmd=[sys.executable,"-m","uvicorn","live_g3_api:app",
         "--app-dir",str(Path(__file__).parent),"--host","127.0.0.1",
         "--port",str(api_port),"--no-access-log","--log-level","error"]
    worker=subprocess.Popen([sys.executable,str(Path(__file__).parent/"worker.py")],
                            env=env,stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    api=subprocess.Popen(cmd,env=env,stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    base=f"http://127.0.0.1:{api_port}"
    try:
        async with httpx.AsyncClient(base_url=base,timeout=90) as client:
            await ready(client,api)
            model=env["POC_C_LITELLM_MODEL"]
            c=await client.post("/v1/responses",
                                json={"model":model,
                                      "input":"用一句中文简单解释为什么事件流需要持久化，再补一句关于任务恢复。不要使用 Markdown。",
                                      "stream":False})
            ack_fault=os.environ.get("POC_C15_INJECT_START_ACK_LOSS")=="1"
            if ack_fault:
                if c.status_code!=503 or c.json().get("detail",{}).get("kind")!="START_ACK_UNKNOWN":
                    raise AssertionError("Native ACK loss was not classified correctly")
                run=c.json()["detail"]["run_id"]
                resolved=await client.post(f"/v1/responses/{run}/reconcile-start")
                if resolved.status_code!=200 or not resolved.json()["native_start_confirmed"]:
                    raise AssertionError("Start ACK loss could not reconcile same native Workflow")
            else:
                if c.status_code!=201:
                    raise AssertionError("Native start/create failed HTTP "+str(c.status_code))
                run=c.json()["id"]
            events=[]
            async with client.stream("GET",f"/v1/responses/{run}/events",timeout=135) as response:
                if response.status_code!=200:raise AssertionError("SSE HTTP "+str(response.status_code))
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        events.append(json.loads(line[6:]))
                    if len(events)>400:
                        raise AssertionError("Unexpectedly large SSE event loop")
            state=(await client.get(f"/v1/responses/{run}")).json()
            kinds=[e["type"] for e in events]
            failed=fake and os.environ.get("POC_C15_FAIL_AFTER_TOKEN")=="1"
            expected_tail=(["run.terminal"] if failed else
                           ["response.output_text.done","verification.passed","run.terminal"])
            if (state["status"]!=("failed" if failed else "completed") or
                kinds[:3]!=["run.started","plan.created","activity.started"] or
                kinds[-len(expected_tail):]!=expected_tail or
                kinds.count("response.output_text.delta")<2 or
                (failed and "verification.passed" in kinds)):
                raise AssertionError("G3 lifecycle status="+state["status"]+" types="+",".join(kinds))
            text="".join(e["data"]["delta"] for e in events
                         if e["type"]=="response.output_text.delta")
            output=state["output"][0]["content"][0]["text"]
            if not text or text!=output:
                raise AssertionError("HTTP GET output differs from persisted SSE tokens")

        # Verify no generated text was inserted into Temporal's native History;
        # model prompt/step IDs may appear there as frozen inputs, but output
        # tokens are Harness-owned PostgreSQL events only.
        import psycopg
        from temporalio.client import Client
        with psycopg.connect(env["POC_C_PLATFORM_DSN"]) as pg:
            native_id=pg.execute(
                "SELECT native_workflow_id FROM poc_c15_runs WHERE run_id=%s",
                (run,)).fetchone()[0]
        native=await Client.connect(env.get("POC_C_TEMPORAL_ADDRESS","127.0.0.1:17234"))
        history=(await native.get_workflow_handle(native_id).fetch_history()).to_json()
        history_blob=history if isinstance(history,str) else json.dumps(history)
        if len(text)>20 and text in history_blob:
            raise AssertionError("Provider output leaked into Temporal Native History")
        cursor=events[2]["id"]
        stop(api);api=None
        api=subprocess.Popen(cmd,env=env,stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        async with httpx.AsyncClient(base_url=base,timeout=90) as client:
            await ready(client,api)
            replay=(await client.get(f"/v1/responses/{run}/events",
                                     headers={"Last-Event-ID":cursor})).text
            if replay.count("event: ")!=len(events)-3:
                raise AssertionError("HTTP restart replay cursor dropped persisted token Events")
            wrong=await client.get(f"/v1/responses/{run}/events",
                                  headers={"Last-Event-ID":"another-run:1"})
            if wrong.status_code!=422:raise AssertionError("Cross-Run SSE cursor accepted")
            if fake and os.environ.get("POC_C15_TEST_CANCEL")=="1":
                created=await client.post("/v1/responses",json={
                    "model":model,"input":"Controlled cancellation fixture","stream":False})
                if ack_fault:
                    if created.status_code!=503:
                        raise AssertionError("Cancellation fixture ACK fault not injected")
                    cancelled_id=created.json()["detail"]["run_id"]
                    r=await client.post(f"/v1/responses/{cancelled_id}/reconcile-start")
                    if r.status_code!=200:
                        raise AssertionError("Cancellation fixture Native Start not reconciled")
                else:
                    if created.status_code!=201:
                        raise AssertionError("Cancellation fixture Create failed")
                    cancelled_id=created.json()["id"]
                cancelled=await client.post(f"/v1/responses/{cancelled_id}/cancel")
                expected_native=("UNKNOWN" if os.environ.get("POC_C15_INJECT_CANCEL_SIGNAL_LOSS")=="1"
                                 else "ACKNOWLEDGED")
                if (cancelled.status_code!=202 or cancelled.json()["status"]!="cancelling"
                        or cancelled.json()["native_cancel"]!=expected_native):
                    raise AssertionError("Cancellation request prematurely finalized or lost ACK classification")
                snapshot=(await client.get(f"/v1/responses/{cancelled_id}")).json()
                if (snapshot["status"]!="in_progress" or
                    snapshot["harness"]["state"]!="CANCELLING"):
                    raise AssertionError("Cancel ACK was incorrectly upgraded to TERMINATED")
                # Verify true Native status via official describe, never
                # equate SDK cancel ACK or provider timeout to execution stop.
                final=None
                for _ in range(65):
                    check=await client.post(f"/v1/responses/{cancelled_id}/reconcile-cancel")
                    if check.status_code==200:
                        final=check.json()
                        break
                    if check.status_code not in (202,409):
                        raise AssertionError("Unsafe Native reconciliation "+str(check.status_code))
                    await asyncio.sleep(.15)
                if not final or not final["confirmed"] or final["status"]!="cancelled":
                    raise AssertionError("Native termination confirmation missing: "+repr(final))
                repeat=await client.post(f"/v1/responses/{cancelled_id}/cancel")
                if repeat.status_code!=200 or repeat.json()["status"]!="cancelled":
                    raise AssertionError("Cancellation was not idempotent")
                cancelled_snapshot=await client.get(f"/v1/responses/{cancelled_id}")
                if cancelled_snapshot.json()["status"]!="cancelled":
                    raise AssertionError("Native completion wrongly overrode platform cancellation")
                history=(await client.get(f"/v1/responses/{cancelled_id}/events")).text
                for kind in ("cancellation.requested","cancellation.confirmed","run.terminal"):
                    if "event: "+kind not in history:
                        raise AssertionError("Missing durable cancellation Typed Event "+kind)
                if history.count("event: cancellation.requested")!=1:
                    raise AssertionError("Duplicate cancellation request facts")

            if fake and not ack_fault and os.environ.get("POC_C15_TEST_STREAM_CREATE")=="1":
                async with client.stream("POST","/v1/responses",json={
                    "model":model,"input":"Response stream:true fixture","stream":True}) as sr:
                    if sr.status_code!=200:
                        raise AssertionError("POST stream:true not supported")
                    stream_text=await sr.aread()
                    if b"event: response.output_text.delta" not in stream_text or b"event: run.terminal" not in stream_text:
                        raise AssertionError("POST stream:true lacks real persisted events")
            again=(await client.get(f"/v1/responses/{run}")).json()
            if again!=state:raise AssertionError("HTTP restart response differs from PG state")
        return {
            "status":"PASS_C15_G3_REAL_MODEL_TO_HTTP_TYPED_TOKEN_SSE" if not fake
                     else "PASS_C15_G3_OFFLINE_FAKE_FAILURE_CONTRACT" if failed
                     else "PASS_C15_G3_OFFLINE_FAKE_MODEL_HTTP_CONTRACT",
            "real_model":not fake,
            "native_temporal_worker":True,"selfhost_HTTP_create_get":True,
            "persisted_typed_event_types":kinds[:3]+["response.output_text.delta"]+kinds[-len(expected_tail):],
            "token_delta_count":kinds.count("response.output_text.delta"),
            "model_response_character_count":len(text),
            "http_restart_last_event_id_replay":True,
            "forged_cursor_rejected":True,
            "final_platform_state":state["harness"]["state"],
            "platform_attempt_id_present":bool(state["harness"]["attempt_id"]),
            "provider_raw_text_in_native_history":False,
            "native_history_output_leak_checked":True,
            "all_harness_tool_approval_artifact_types_proven":False,
            "cancel_test_proven":fake and os.environ.get("POC_C15_TEST_CANCEL")=="1",
            "ack_loss_reconciliation_proven":os.environ.get("POC_C15_INJECT_START_ACK_LOSS")=="1",
            "cancel_fixture_proven":fake and os.environ.get("POC_C15_TEST_CANCEL")=="1",
        }
    finally:
        stop(api);stop(worker)

if __name__=="__main__":
    try:print(json.dumps(asyncio.run(exercise()),sort_keys=True,ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"status":"G3_E2E_GAP","exception_type":type(exc).__name__}))
        raise