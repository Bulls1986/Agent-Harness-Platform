"""C13: real native Temporal OpenTelemetry + stable Harness PG task IDs.

Memory exporter stands in for external Collector and is NOT an APM backend.
No prompt, model response, secrets, history or telemetry payload retention.
"""
from __future__ import annotations

import asyncio
import json
import os
from uuid import uuid4

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import ALWAYS_ON
from temporalio import activity
from c13_workflow import ObservedRuntimeWorkflow
from temporalio.client import Client
from temporalio.contrib.opentelemetry import OpenTelemetryInterceptor, create_tracer_provider
from temporalio.worker import Worker

from runtime_swap_facts import RuntimeFacts,RuntimeRun

# Explicit instrumentation of Harness OWNED boundaries only. Native Workflow/
# Activity spans come from the official Temporal SDK interceptor.
@activity.defn(name="c13_bounded_harness_activity")
async def harness_execution(request:dict)->dict:
    stage=request["stage"]
    tracer=trace.get_tracer("harness.c13")
    with tracer.start_as_current_span("harness.execution",attributes={
        "harness.run.id":request["run_id"],
        "harness.step.id":stage["step_id"],
        "harness.attempt.id":stage["attempt_id"],
        "harness.execution.id":stage["execution_id"],
        "harness.runtime.adapter":stage["adapter"],
    }):
        store=RuntimeFacts(os.environ["POC_C_PLATFORM_DSN"])
        store.require_frozen(request,stage)
        result=store.verify(request["run_id"],stage,request["expected_marker"],12)
        if not result["passed"]:raise ValueError("fixture failed")
        return {"adapter":stage["adapter"],"attempt_id":stage["attempt_id"],
                "verified":True}

@activity.defn(name="c13_bounded_harness_finalize")
async def harness_finalize(request:dict)->dict:
    store=RuntimeFacts(os.environ["POC_C_PLATFORM_DSN"])
    with trace.get_tracer("harness.c13").start_as_current_span(
        "harness.run.finalize",attributes={"harness.run.id":request["run_id"]}):
        return store.complete(request["run_id"])

async def run_once() -> dict:
    if not os.environ.get("POC_C_PLATFORM_DSN"):
        raise AssertionError("Independent Harness PostgreSQL required")
    exporter=InMemorySpanExporter()
    provider=create_tracer_provider(
        resource=Resource.create({"service.name":"poc-c13-temporal-worker"}),
        sampler=ALWAYS_ON)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    store=RuntimeFacts(os.environ["POC_C_PLATFORM_DSN"])
    store.initialize()
    run=RuntimeRun.build()
    store.prepare(run)
    client=await Client.connect(
        os.environ.get("POC_C_TEMPORAL_ADDRESS","127.0.0.1:17234"),
        interceptors=[OpenTelemetryInterceptor(add_temporal_spans=True)])
    queue="poc-c13-otel-"+uuid4().hex[:12]
    worker=Worker(client,task_queue=queue,
                  workflows=[ObservedRuntimeWorkflow],
                  activities=[harness_execution,harness_finalize],
                  interceptors=[OpenTelemetryInterceptor(add_temporal_spans=True)])
    with trace.get_tracer("harness.c13").start_as_current_span(
        "harness.run.start",attributes={"harness.run.id":run.run_id}):
        async with worker:
            handle=await client.start_workflow(
                ObservedRuntimeWorkflow.run,run.request(),
                id=run.native_workflow_id,task_queue=queue)
            result=await asyncio.wait_for(handle.result(),timeout=40)
    if result["state"]!="COMPLETED" or len(result["activities"])!=2:
        raise AssertionError("C13 true Temporal worker Workflow failed")
    snapshot=RuntimeFacts(store.dsn).snapshot(run.run_id)
    if snapshot["run"]["state"]!="COMPLETED" or len(snapshot["events"])!=6:
        raise AssertionError("Telemetry must not replace persisted business facts")
    spans=exporter.get_finished_spans()
    names=[s.name for s in spans]
    native=[s for s in spans if s.name not in
            {"harness.execution","harness.run.start","harness.run.finalize"}]
    attrs=[s.attributes for s in spans if s.name=="harness.execution"]
    if len(attrs)!=2 or not native:
        raise AssertionError("C13 requires two Harness correlation spans and native Temporal spans")
    if {a["harness.attempt.id"] for a in attrs}!={s.attempt_id for s in run.stages}:
        raise AssertionError("Activity OTel correlation missing persisted Attempt IDs")
    if {a["harness.execution.id"] for a in attrs}!={s.execution_id for s in run.stages}:
        raise AssertionError("Activity OTel correlation missing persisted Execution IDs")
    if any(a["harness.run.id"]!=run.run_id for a in attrs):
        raise AssertionError("Cross-activity Run correlation not stable")
    if any(s.context.trace_id==0 or s.context.span_id==0 for s in native):
        raise AssertionError("Temporal native traces did not use OTel context")
    provider.force_flush()
    # Sanitize: no raw data, private endpoint, model prompt or native payload.
    observed_native_names=sorted(set(s.name for s in native))
    output={
        "status":"PASS_C13_TEMPORAL_NATIVE_OTEL_AND_HARNESS_CORRELATION",
        "real_native_temporal_workflow":True,
        "otel_interceptor":"temporalio.contrib.opentelemetry.OpenTelemetryInterceptor",
        "otel_exporter":"in_memory_POC_collector_stub",
        "native_span_count":len(native),
        "native_span_names":observed_native_names,
        "harness_execution_spans":len(attrs),
        "correlated_run_count":1,"correlated_attempt_count":2,
        "correlated_execution_count":2,
        "harness_persisted_event_count":len(snapshot["events"]),
        "business_facts_held_by":"Harness PostgreSQL",
        "telemetry_is_domain_state":False,
        "production_OTLP_collector_verified":False,
        "production_observability_backend_verified":False,
    }
    provider.shutdown()
    return output


if __name__=="__main__":
    print(json.dumps(asyncio.run(run_once()),sort_keys=True))
