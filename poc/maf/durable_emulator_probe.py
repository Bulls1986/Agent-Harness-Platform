"""A31–A33 MAF native Durable Workflow + DTS Emulator crash/handoff probe.

This *uses the actual Microsoft Durable Extension*:
  DurableAIAgentWorker.configure_workflow()
  DurableWorkflowClient.start_workflow/get_pending_hitl_requests/send_hitl_response()
There are deliberately NO model calls, no alternate scheduler, no direct
checkpoint parsing, and no production cloud assumptions. The host filesystem
marker verifies the number of fixture Executor invocations; it is not a
Runtime State backend, and is not protected from physical host failure.
"""
from __future__ import annotations

import argparse
import asyncio
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys
import time
from typing import Never

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler, response_handler
from agent_framework_durabletask import DurableAIAgentWorker, DurableWorkflowClient
from durabletask.azuremanaged.worker import DurableTaskSchedulerWorker
from durabletask.azuremanaged.client import DurableTaskSchedulerClient

WORKFLOW_NAME = "maf-poc-a33-native-durable-hitl-v1"
HOST_ADDRESS = os.environ.get("POC_DTS_ENDPOINT", "http://127.0.0.1:18080")
TASKHUB = os.environ.get("POC_DTS_TASKHUB", "pocmaf")
ALLOWED_CASES = ("approved-fixture", "rejected-fixture")


def marker_path(name: str, kind: str) -> Path:
    if name not in ALLOWED_CASES or kind not in ("prepare", "action"):
        raise ValueError("Unknown trusted fixture")
    root = Path(os.environ["POC_DTS_MARKERS"])
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{name}.{kind}"


def marker(name: str, kind: str) -> None:
    # Controlled CI fixture. These marker writes are *not* part of the
    # runtime checkpoint transaction or a claimed exactly-once side effect.
    with marker_path(name, kind).open("a", encoding="utf-8") as f:
        f.write("called\n")


class PrepareExecutor(Executor):
    @handler
    async def prepare(self, case: str, ctx: WorkflowContext[str]) -> None:
        if case not in ALLOWED_CASES:
            raise ValueError("Invalid fixture")
        marker(case, "prepare")
        await ctx.send_message(case)


class GateExecutor(Executor):
    @handler
    async def request(self, case: str, ctx: WorkflowContext[str, str]) -> None:
        if case not in ALLOWED_CASES:
            raise ValueError("Invalid fixture")
        await ctx.request_info(request_data=f"approval:{case}", response_type=str)

    @response_handler
    async def receive(self, original_request: str, response: str,
                      ctx: WorkflowContext[str, str]) -> None:
        if original_request not in ("approval:approved-fixture", "approval:rejected-fixture"):
            raise ValueError("Native request mismatch")
        if response == "APPROVED":
            await ctx.send_message(original_request.split(":", 1)[1])
        elif response == "REJECTED":
            await ctx.yield_output("DENIED_NO_EXECUTION")
        else:
            raise ValueError("Unrecognized decision")


class SensitiveFixtureExecutor(Executor):
    @handler
    async def act(self, case: str, ctx: WorkflowContext[Never, str]) -> None:
        if case not in ALLOWED_CASES:
            raise ValueError("Unknown approval case")
        marker(case, "action")
        await ctx.yield_output(f"SIMULATED_EXECUTION:{case}")


def workflow():
    a = PrepareExecutor(id="fixture-prepare")
    b = GateExecutor(id="fixture-approval-gate")
    c = SensitiveFixtureExecutor(id="fixture-controlled-action")
    return (WorkflowBuilder(name=WORKFLOW_NAME, start_executor=a)
            .add_edge(a, b).add_edge(b, c).build())


def task_worker():
    return DurableTaskSchedulerWorker(host_address=HOST_ADDRESS,
                                      secure_channel=False,taskhub=TASKHUB,
                                      token_credential=None)


def task_client():
    return DurableWorkflowClient(
        DurableTaskSchedulerClient(host_address=HOST_ADDRESS,
                                   secure_channel=False,taskhub=TASKHUB,
                                   token_credential=None),
        workflow_name=WORKFLOW_NAME,
    )


def serve() -> None:
    worker=task_worker()
    host=DurableAIAgentWorker(worker)
    host.configure_workflow(workflow())
    worker.start()
    print(json.dumps({"worker_ready": True,"workflow": WORKFLOW_NAME}),flush=True)
    while True:
        time.sleep(1)


def wait_pending(instance_id: str, *, seconds: int) -> dict:
    client=task_client()
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        pending=client.get_pending_hitl_requests(instance_id)
        if pending:
            if len(pending)!=1 or "request_id" not in pending[0]:
                raise RuntimeError("Expected exactly one native HITL request")
            return {"instance_id":instance_id,"request_id":pending[0]["request_id"],
                    "source_executor_id":pending[0].get("source_executor_id"),
                    "pending":True}
        status=client.get_runtime_status(instance_id)
        if str(status).upper() in ("COMPLETED","FAILED","TERMINATED"):
            raise RuntimeError(f"Terminal before HITL: {status}")
        time.sleep(1)
    raise TimeoutError("No native HITL request within deadline")


def main() -> int:
    parser=argparse.ArgumentParser()
    commands=parser.add_subparsers(dest="command",required=True)
    commands.add_parser("worker")
    commands.add_parser("version")
    start=commands.add_parser("start")
    start.add_argument("--case",required=True,choices=ALLOWED_CASES)
    pending=commands.add_parser("pending")
    pending.add_argument("--instance",required=True)
    pending.add_argument("--timeout",type=int,default=70)
    respond=commands.add_parser("respond")
    respond.add_argument("--instance",required=True)
    respond.add_argument("--request",required=True)
    respond.add_argument("--decision",choices=("APPROVED","REJECTED"),required=True)
    output=commands.add_parser("output")
    output.add_argument("--instance",required=True)
    args=parser.parse_args()
    if args.command=="worker":
        serve()
        return 0
    if args.command=="version":
        print(json.dumps({
            "agent_framework_core":version("agent-framework-core"),
            "agent_framework_durabletask":version("agent-framework-durabletask"),
            "durabletask_azuremanaged":version("durabletask-azuremanaged"),
        },sort_keys=True))
    elif args.command=="start":
        print(json.dumps({"instance_id":task_client().start_workflow(input=args.case)}),flush=True)
    elif args.command=="pending":
        print(json.dumps(wait_pending(args.instance,seconds=args.timeout)),flush=True)
    elif args.command=="respond":
        task_client().send_hitl_response(args.instance,args.request,args.decision)
        print(json.dumps({"response_sent":True,"decision":args.decision}),flush=True)
    elif args.command=="output":
        response=task_client().await_workflow_output(args.instance)
        print(json.dumps({"output":str(response)},sort_keys=True),flush=True)
    return 0


if __name__=="__main__":
    sys.exit(main())
