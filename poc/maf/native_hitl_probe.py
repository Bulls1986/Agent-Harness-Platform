"""A26 native MAF request_info -> platform Approval -> native checkpoint resume.

No model calls, shell or external tools. A trusted CI fixture maps the MAF
request_id and opaque checkpoint ID to a platform Approval atomically.
The simulated sensitive tool is a distinct Executor and executes only after
the platform Approval store commits APPROVED. Production authorization must
come from the enterprise Policy boundary, not from this CLI.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Never

from agent_framework import (
    Executor, FileCheckpointStorage, WorkflowBuilder, WorkflowContext,
    handler, response_handler,
)

from approval_wait import ApprovalWaitStore
from approval_delivery import ApprovalDelivery, DeliveryConflict
from task_ledger import TaskLedger
from workflow_probe import VerificationFact

WORKFLOW_NAME = "maf-native-approval-poc-v1"
APPROVAL_ACTION = "tool:external-write-demo"
APPROVAL_RESOURCE = "resource:trusted-ci-demo"
APPROVAL_POLICY = "policy:poc-approval"
APPROVER = "poc-native-approved-principal"


class NativeApprovalExecutor(Executor):
    @handler
    async def ask(self, value: str, ctx: WorkflowContext[str, str]) -> None:
        if value != "ci-gated-action":
            raise ValueError("Not a trusted native HITL fixture")
        await ctx.request_info(
            request_data="approve-or-reject:" + APPROVAL_ACTION,
            response_type=str,
        )

    @response_handler
    async def on_decision(
        self, original_request: str, decision: str, ctx: WorkflowContext[str, str]
    ) -> None:
        if original_request != "approve-or-reject:" + APPROVAL_ACTION:
            raise ValueError("Native response request mismatch")
        if decision == "APPROVED":
            await ctx.send_message("authorized-by-platform")
        elif decision == "REJECTED":
            await ctx.yield_output("DENIED_NO_EXECUTION")
        else:
            raise ValueError("Invalid native HITL response")


class SimulatedSensitiveExecution(Executor):
    @handler
    async def run_action(
        self, value: str, ctx: WorkflowContext[Never, str]
    ) -> None:
        if value != "authorized-by-platform":
            raise ValueError("Untrusted gate bypass")
        # Controlled Data Plane fixture only; no external side effect.
        await ctx.yield_output("SIMULATED_EXECUTION")


def build(storage: FileCheckpointStorage):
    gate=NativeApprovalExecutor(id="platform-approval-gate")
    tool=SimulatedSensitiveExecution(id="simulated-sensitive-execution")
    return (
        WorkflowBuilder(
            name=WORKFLOW_NAME, start_executor=gate, checkpoint_storage=storage
        ).add_edge(gate,tool).build()
    )


def storage_at(root: Path) -> FileCheckpointStorage:
    return FileCheckpointStorage(str(root / "native-workflow-checkpoints"))


async def create(root: Path, dsn: str) -> dict:
    root.mkdir(parents=True,exist_ok=True)
    TaskLedger(dsn).initialize()
    store=ApprovalWaitStore(dsn)
    storage=storage_at(root)
    workflow=build(storage)
    requests=[]
    outputs=[]
    async for event in workflow.run("ci-gated-action",stream=True):
        if event.type == "request_info":
            requests.append(event)
        elif event.type == "output":
            outputs.append(event.data)
    if len(requests)!=1 or outputs:
        raise RuntimeError("Expected exactly one pending MAF HITL event and no action")
    latest=await storage.get_latest(workflow_name=workflow.name)
    if latest is None or not latest.checkpoint_id:
        raise RuntimeError("MAF did not persist pending request checkpoint")
    fact=VerificationFact.example(passed=False,evidence_ref=None)
    approval=store.request(
        fact,requester_principal="poc-native-requester",
        approver_principal=APPROVER,
        action_ref=APPROVAL_ACTION,
        resource_ref=APPROVAL_RESOURCE,
        policy_ref=APPROVAL_POLICY,
        native_request_id=requests[0].request_id,
        native_checkpoint_ref=latest.checkpoint_id,
        native_workflow_name=WORKFLOW_NAME,
    )
    return {
        "run_id":approval.run_id,
        "approval_id":approval.approval_id,
        "state":approval.state,
        "native_request_bound":True,
        "preapproval_execution_count":len(outputs),
    }


async def continue_after_restart(
    root: Path, dsn: str, run_id: str, decision: str,
    *, inject_after_decision: bool = False,
    inject_after_claim: bool = False,
) -> dict:
    """Resume after committed Approval; do not repeat an uncertain Runtime response.

    Two explicit fault injection points distinguish a safe pre-delivery crash
    from the unsafe post-intent crash. The latter becomes UNKNOWN and requires
    reconciliation rather than blindly invoking a sensitive tool twice.
    """
    if decision not in ("APPROVED","REJECTED"):
        raise ValueError("Unsupported decision")
    store=ApprovalWaitStore(dsn)
    deliveries=ApprovalDelivery(dsn)
    try:
        pending=store.load_pending(run_id)
        binding=store.load_native_binding(run_id)
        already_decided=False
        if pending.approval_id!=binding["approval_id"]:
            raise ValueError("Native binding does not match pending Approval")
    except KeyError:
        binding=deliveries.load_decided(run_id)
        if binding["decision"]!=decision:
            raise DeliveryConflict("Cannot change already persisted Approval decision")
        already_decided=True
    if binding["native_workflow_name"]!=WORKFLOW_NAME:
        raise ValueError("MAF Workflow identity mismatch")
    storage=storage_at(root)
    known=await storage.list_checkpoints(workflow_name=WORKFLOW_NAME)
    if binding["native_checkpoint_ref"] not in {c.checkpoint_id for c in known}:
        raise ValueError("Opaque native checkpoint is no longer available")

    workflow=build(storage)
    emitted=[]
    unexpected_outputs=[]
    async for event in workflow.run(
        checkpoint_id=binding["native_checkpoint_ref"],stream=True
    ):
        if event.type=="request_info":
            emitted.append(event.request_id)
        elif event.type=="output":
            unexpected_outputs.append(event.data)
    if emitted!=[binding["native_request_id"]] or unexpected_outputs:
        raise ValueError("Recovered MAF request differs from persisted platform Approval")

    if not already_decided:
        state=store.decide(
            pending.approval_id,authenticated_principal=APPROVER,
            authorized=True,decision=decision,
        )
    else:
        state="RUNNING" if decision=="APPROVED" else "FAILED"

    if inject_after_decision:
        # CI process dies AFTER PostgreSQL decision commit, BEFORE Runtime
        # resume intent; another worker can recover it without new approval.
        os._exit(92)

    claim=deliveries.claim(run_id)
    if claim.state=="UNKNOWN_REQUIRES_RECONCILIATION":
        raise DeliveryConflict("UNKNOWN native delivery; no blind replay allowed")
    if claim.state=="ALREADY_APPLIED":
        return {
            "same_run":True, "native_request_matched":True,
            "native_checkpoint_restored":True, "decision":decision,
            "platform_run_state":state,
            "sensitive_execution_simulated":False,
            "already_applied":True,
            "outputs":[claim.output_kind],
        }
    if inject_after_claim:
        # A crash after response delivery was authorized may leave an unknown
        # side effect; subsequent process MUST NOT replay this request.
        os._exit(93)
    outputs=[]
    async for event in workflow.run(
        stream=True, responses={binding["native_request_id"]:decision}
    ):
        if event.type=="output":
            outputs.append(event.data)
    expected="SIMULATED_EXECUTION" if decision=="APPROVED" else "DENIED_NO_EXECUTION"
    if outputs!=[expected]:
        raise RuntimeError(f"Unexpected postapproval output: {outputs!r}")
    deliveries.complete(run_id,token=claim.token,output_kind=expected)
    facts=TaskLedger(dsn).read(run_id)
    if facts["run"]["state"] != state:
        raise RuntimeError("Platform Run state changed unexpectedly")
    return {
        "same_run":facts["run"]["run_id"]==run_id,
        "native_request_matched":True, "native_checkpoint_restored":True,
        "decision":decision, "platform_run_state":state,
        "sensitive_execution_simulated":expected=="SIMULATED_EXECUTION",
        "already_applied":False, "outputs":outputs,
    }


def main() -> int:
    parser=argparse.ArgumentParser()
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--create",action="store_true")
    group.add_argument("--resume",metavar="RUN_ID")
    parser.add_argument("--checkpoint-root",type=Path,required=True)
    parser.add_argument("--decision",choices=("APPROVED","REJECTED"))
    parser.add_argument("--inject-after-decision",action="store_true")
    parser.add_argument("--inject-after-claim",action="store_true")
    args=parser.parse_args()
    dsn=os.environ.get("POC_POSTGRES_DSN")
    if not dsn:
        raise ValueError("POC_POSTGRES_DSN is required")
    if args.resume and not args.decision:
        parser.error("--resume requires --decision")
    result=asyncio.run(
        create(args.checkpoint_root,dsn) if args.create
        else continue_after_restart(
            args.checkpoint_root,dsn,args.resume,args.decision,
            inject_after_decision=args.inject_after_decision,
            inject_after_claim=args.inject_after_claim,
        )
    )
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
