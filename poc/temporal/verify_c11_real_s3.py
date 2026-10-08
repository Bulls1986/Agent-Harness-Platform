"""C11 actual two Docker adapters, real SeaweedFS S3 and Harness PG.

No provider credentials, output bytes or Native History stored by Harness.
"""
from __future__ import annotations
import asyncio
import hashlib
import json
import os
from uuid import uuid4

from temporalio.client import Client
from temporalio.worker import Worker

from c11_facts import C11Facts,C11Run
from c11_object_store import S3PayloadStore
from c11_sandbox_spi import IMAGE,_docker,PAYLOAD_SIZE
from c11_workflow import SandboxArtifactWorkflow
from c11_activities import sandbox_to_objectstore,verify_s3_evidence,finalize_run


async def main()->dict:
    dsn=os.environ["POC_C_PLATFORM_DSN"]
    store=S3PayloadStore()
    facts=C11Facts(dsn)
    facts.initialize()
    image_digest=_docker("image","inspect","--format","{{.Id}}",IMAGE)
    run=C11Run.build(image_digest)
    facts.prepare(run)
    # Neither SandboxProvider nor S3 gets imported by native Workflow.
    client=await Client.connect(os.environ.get("POC_C_TEMPORAL_ADDRESS",
                                                "127.0.0.1:17234"))
    worker=Worker(client,task_queue="poc-c11-"+uuid4().hex[:12],
                  workflows=[SandboxArtifactWorkflow],
                  activities=[sandbox_to_objectstore,verify_s3_evidence,
                              finalize_run])
    async with worker:
        handle=await client.start_workflow(
            SandboxArtifactWorkflow.run,run.request(),
            id=run.native_workflow_id,task_queue=worker.task_queue)
        result=await asyncio.wait_for(handle.result(),timeout=185)
    if result["state"]!="COMPLETED" or not result["artifact_refs_only"]:
        raise AssertionError("Temporal Workflow failed to verify both Sandbox providers")
    payloads=facts.rows(run.run_id)
    if len(payloads)!=4 or sorted(x["kind"] for x in payloads)!=[
            "ARTIFACT","ARTIFACT","EVIDENCE","EVIDENCE"]:
        raise AssertionError("Missing 2 logical Artifact and 2 independent Evidence IDs")
    if not all(x["payload_status"]=="AVAILABLE" and x["recovery_pinned"] for x in payloads):
        raise AssertionError("Active Artifact/Evidence payload incorrectly unpinned")
    for row in payloads:
        actual=store.read(row["storage_ref"])
        if len(actual)!=row["size_bytes"] or hashlib.sha256(actual).hexdigest()!=row["sha256_hex"]:
            raise AssertionError("Object storage digest does not match Harness metadata")
    with __import__("psycopg").connect(dsn) as db:
        events=db.execute("SELECT seq,event_type,payload FROM poc_events WHERE run_id=%s ORDER BY seq",
                          (run.run_id,)).fetchall()
    types=[x[1] for x in events]
    if types!=["run.started","artifact.created","verification.passed",
              "artifact.created","verification.passed","run.terminal"]:
        raise AssertionError("Actual Harness Artifact/Evidence Typed Events out of order")
    history=await handle.fetch_history()
    raw=history.to_json()
    if isinstance(raw,str):
        serialized=raw.encode()
    else:
        serialized=json.dumps(raw).encode()
    if len(serialized)>=130_000:
        raise AssertionError("Native Workflow History contains too much payload data")
    if "C11-PAYLOAD-OK!!" in serialized.decode(errors="ignore"):
        raise AssertionError("Native History leaked actual sandbox payload")
    # Explicit trusted release then purge: S3 payload is deleted, platform
    # retains lineage/digest/size/tombstone. No implicit GC or retention engine.
    chosen=next(x for x in payloads if x["kind"]=="ARTIFACT")
    ref=chosen["storage_ref"]
    try:
        facts.purge(chosen["payload_id"])
        raise AssertionError("Pinned Artifact incorrectly allowed purge")
    except __import__("psycopg").Error:
        pass
    facts.release_pin(chosen["payload_id"])
    store.delete(ref)
    facts.purge(chosen["payload_id"])
    tombstone=next(x for x in facts.rows(run.run_id) if x["payload_id"]==chosen["payload_id"])
    if (tombstone["payload_status"]!="PURGED" or
        tombstone["storage_ref"] is not None or
        tombstone["purged_at"] is None or
        tombstone["sha256_hex"]!=chosen["sha256_hex"]):
        raise AssertionError("Artifact tombstone lost immutable lineage/digest")
    return {
        "status":"PASS_C11_REAL_DOCKER_SANDBOX_S3_ARTIFACT_LINEAGE",
        "sandbox_adapters":["docker-oneshot","docker-session"],
        "distinct_sandbox_infrastructure_proven":False,
        "cube_sandbox_production_proven":False,
        "actual_container_isolation":True,
        "actual_s3_object_store":True,
        "object_store_provider":"SeaweedFS S3 3.99",
        "platform_run_state":"COMPLETED",
        "platform_attempts":2,
        "logical_artifact_count":2,
        "logical_evidence_count":2,
        "payload_bytes_per_artifact":PAYLOAD_SIZE,
        "native_history_serialized_bytes":len(serialized),
        "platform_event_types":types,
        "retention_pin_blocks_purge":True,
        "explicit_purge_leaves_metadata_tombstone":True,
        "raw_artifact_payload_in_native_history":False,
    }


if __name__=="__main__":
    try:
        print(json.dumps(asyncio.run(main()),sort_keys=True))
    except Exception as exc:
        # URL/credentials must not appear in diagnostics.
        print(json.dumps({"status":"C11_GAP","exception_type":type(exc).__name__}))
        raise
