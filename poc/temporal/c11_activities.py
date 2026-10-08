"""C11 real isolated SandboxProvider -> S3 payload -> Harness PG metadata.

Only Activity/Data Plane can touch Docker/S3/PG; Workflow receives IDs.
No large object payload in Native History and no host shell commands from
Agent-generated input: fixtures are controlled inside the trusted adapter.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os

from temporalio import activity
from c11_facts import C11Facts
from c11_object_store import S3PayloadStore
from c11_sandbox_spi import DockerSandboxProvider


@activity.defn(name="c11_sandbox_to_objectstore")
async def sandbox_to_objectstore(request:dict)->dict:
    stage=request["stage"]
    facts=C11Facts(os.environ["POC_C_PLATFORM_DSN"])
    await asyncio.to_thread(facts.frozen,request,stage)
    output=await asyncio.to_thread(DockerSandboxProvider(stage["provider"]).execute)
    if (output.image_digest!=request["frozen_image_digest"] or
            not output.network_disabled or not output.read_only_rootfs):
        raise ValueError("C11 sandbox execution violated frozen isolation environment")
    digest=hashlib.sha256(output.blob).hexdigest()
    key=f"runs/{request['run_id']}/{stage['execution_id']}/artifact-{digest}.bin"
    ref=await asyncio.to_thread(S3PayloadStore().put,key,output.blob)
    artifact_id=await asyncio.to_thread(
        facts.record_artifact,request,stage,digest,len(output.blob),ref)
    return {"artifact_id":artifact_id,"provider":stage["provider"],
            "sha256":digest,"size_bytes":len(output.blob),
            "storage_ref":ref,"environment_fingerprint":output.image_digest}


@activity.defn(name="c11_verify_s3_evidence")
async def verify_s3_evidence(request:dict)->dict:
    stage=request["stage"]
    facts=C11Facts(os.environ["POC_C_PLATFORM_DSN"])
    await asyncio.to_thread(facts.frozen,request,stage)
    obj=await asyncio.to_thread(facts.artifact,request,stage)
    if obj["payload_id"]!=request["artifact_id"]:
        raise ValueError("C11 forged Artifact ID")
    store=S3PayloadStore()
    actual=await asyncio.to_thread(store.read,obj["storage_ref"])
    digest=hashlib.sha256(actual).hexdigest()
    if digest!=obj["sha256_hex"] or len(actual)!=obj["size_bytes"]:
        raise ValueError("Independent S3 Payload digest verification FAILED")
    # Small evidence payload physically in OSS, NOT Runtime History/PG.
    proof=json.dumps({"artifact_id":obj["payload_id"],"sha256":digest,
                      "bytes":len(actual),"verified":True},
                     sort_keys=True).encode()
    evidence_digest=hashlib.sha256(proof).hexdigest()
    ref=await asyncio.to_thread(
        store.put,f"runs/{request['run_id']}/{stage['execution_id']}/"
                  f"evidence-{evidence_digest}.json",proof)
    evidence_id=await asyncio.to_thread(
        facts.verification,request,stage,obj["payload_id"],ref,
        evidence_digest,len(proof))
    return {"passed":True,"evidence_id":evidence_id,
            "artifact_id":obj["payload_id"]}


@activity.defn(name="c11_finalize_run")
async def finalize_run(request:dict)->dict:
    await asyncio.to_thread(C11Facts(os.environ["POC_C_PLATFORM_DSN"]).complete,
                            request["run_id"])
    return {"state":"COMPLETED"}
