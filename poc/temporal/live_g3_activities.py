"""C15 Data Plane: actual model streaming to trusted Harness PG Events.

No agent/tool access, secrets, or model text in Temporal History. CI may set
explicit fake model fixture, never mistaken for real live proof.
"""
from __future__ import annotations
import asyncio
from hashlib import sha256
import os
from temporalio import activity
from live_g3_facts import LiveFacts

@activity.defn(name="c15_stream_model")
async def stream_model(req:dict):
    store=LiveFacts(os.environ["POC_C_PLATFORM_DSN"])
    await asyncio.to_thread(store.require,req)
    started=await asyncio.to_thread(store.append,req,"activity.started",
                       {"step_id":req["step"],"attempt_id":req["attempt"],"execution_id":req["execution"]})
    if not started:return {"cancelled":True}
    pieces=[]
    try:
        if os.environ.get("POC_C15_FAKE_MODEL")=="1":
            # Explicit fake tokens for CI workflow contract only.
            chunks=["C15 ","OFFLINE ","FAKE ","RESPONSE"]
            for token in chunks:
                await asyncio.sleep(float(os.environ.get("POC_C15_FAKE_TOKEN_DELAY","0.07")))
                pieces.append(token)
                ok=await asyncio.to_thread(store.append,req,"response.output_text.delta",{"delta":token})
                if not ok:return {"cancelled":True}
            if os.environ.get("POC_C15_FAIL_AFTER_TOKEN")=="1":
                raise ValueError("Controlled model interruption after token emission")
        else:
            from openai import AsyncOpenAI
            endpoint=os.environ["POC_C_LITELLM_BASE_URL"]
            key=os.environ["JUSDA_LITELLM_API_KEY"]
            async with AsyncOpenAI(base_url=endpoint,api_key=key,timeout=100,max_retries=0) as client:
                result=await client.chat.completions.create(
                    model=req["model"],stream=True,max_tokens=200,
                    messages=[{"role":"user","content":req["prompt"]}])
                async for chunk in result:
                    for choice in chunk.choices:
                        token=choice.delta.content or ""
                        if token:
                            pieces.append(token)
                            ok=await asyncio.to_thread(store.append,req,
                                "response.output_text.delta",{"delta":token})
                            if not ok:return {"cancelled":True}
        text="".join(pieces)
        if not text:raise ValueError("No real model text received")
        digest=sha256(text.encode()).hexdigest()
        ok=await asyncio.to_thread(store.append,req,"response.output_text.done",
                                   {"sha256":digest,"chars":len(text)})
        if not ok:return {"cancelled":True}
        return {"cancelled":False,"digest":digest,"count":len(text)}
    except asyncio.CancelledError:
        # Platform Cancel happens first and remains authoritative.
        raise
    except Exception:
        # Native Activity retry is disabled here. Persist a safe platform
        # failure rather than leave a ghost RUNNING Run after model exception.
        await asyncio.to_thread(store.terminal,req,"FAILED")
        raise

@activity.defn(name="c15_write_s3_artifact")
async def write_s3_artifact(req:dict):
    """Save same-Run persisted Token bytes to S3, not Temporal History."""
    store=LiveFacts(os.environ["POC_C_PLATFORM_DSN"])
    dispatched=False
    try:
        from c11_object_store import S3PayloadStore
        text=await asyncio.to_thread(store.model_text_for_artifact,req,
                                     req["digest"],req["count"])
        blob=text.encode()
        key=f"runs/{req['run']}/{req['execution']}/response-{req['digest']}.txt"
        provider=S3PayloadStore()
        dispatched=True
        ref=await asyncio.to_thread(provider.put,key,blob)
        if os.environ.get("POC_C15_INJECT_S3_WRITE_UNKNOWN")=="1":
            # Injection AFTER physical PUT, BEFORE PG artifact.created ACK.
            raise RuntimeError("Injected S3 write acknowledgement loss")
        artifact=await asyncio.to_thread(store.record_artifact,req,req["digest"],
                                         len(blob),ref)
        if not artifact:return {"cancelled":True}
        return {"cancelled":False,"artifact_id":artifact,
                "sha256":req["digest"],"size_bytes":len(blob),"storage_ref":ref}
    except asyncio.CancelledError:
        raise
    except Exception:
        if dispatched:
            # The S3 object may exist even if POST returned an error. Quarantine
            # immutable Attempt/Execution UNKNOWN, never blind PUT/retry.
            await asyncio.to_thread(store.mark_artifact_unknown,req)
        else:
            await asyncio.to_thread(store.terminal,req,"FAILED")
        raise

@activity.defn(name="c15_verify_s3_artifact")
async def verify_s3_artifact(req:dict):
    """Separate Activity reads the real S3 object and checks SHA-256."""
    store=LiveFacts(os.environ["POC_C_PLATFORM_DSN"])
    try:
        from c11_object_store import S3PayloadStore
        blob=await asyncio.to_thread(S3PayloadStore().read,req["storage_ref"])
        if len(blob)!=req["size_bytes"] or sha256(blob).hexdigest()!=req["sha256"]:
            raise ValueError("Independent S3 Artifact digest mismatch")
        passed=await asyncio.to_thread(store.mark_artifact_verified,req,
                                       req["artifact_id"],req["sha256"],
                                       req["storage_ref"],req["size_bytes"])
        return {"passed":passed}
    except asyncio.CancelledError:
        raise
    except Exception:
        await asyncio.to_thread(store.terminal,req,"FAILED")
        raise

@activity.defn(name="c15_verify_tokens")
async def verify_tokens(req:dict):
    store=LiveFacts(os.environ["POC_C_PLATFORM_DSN"])
    try:
        passed=await asyncio.to_thread(store.verify,req,req["digest"],req["count"])
        return {"passed":passed}
    except asyncio.CancelledError:
        raise
    except Exception:
        await asyncio.to_thread(store.terminal,req,"FAILED")
        raise

@activity.defn(name="c15_finish")
async def finish(req:dict):
    state=await asyncio.to_thread(LiveFacts(os.environ["POC_C_PLATFORM_DSN"]).terminal,req,"COMPLETED")
    return {"state":state}