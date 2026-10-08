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

@activity.defn(name="c15_verify_tokens")
async def verify_tokens(req:dict):
    store=LiveFacts(os.environ["POC_C_PLATFORM_DSN"])
    passed=await asyncio.to_thread(store.verify,req,req["digest"],req["count"])
    return {"passed":passed}

@activity.defn(name="c15_finish")
async def finish(req:dict):
    state=await asyncio.to_thread(LiveFacts(os.environ["POC_C_PLATFORM_DSN"]).terminal,req,"COMPLETED")
    return {"state":state}
