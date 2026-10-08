"""C09 deterministic Temporal Workflow independent of actual Agent SDK.

Only a string Activity type and a frozen adapter descriptor cross the Workflow
boundary. Runtime work (model calls, SDK imports, PG writes) stays in Activity.
"""
from __future__ import annotations
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy


@workflow.defn(name="poc-c09-real-runtime-swap")
class RealRuntimeSwapWorkflow:
    @workflow.run
    async def run(self,request:dict)->dict:
        if set(request)!={"run_id","native_workflow_id","expected_marker",
                         "frozen_workflow_version","stages"}:
            raise ValueError("Unexpected C09 Workflow shape")
        stages=request["stages"]
        if (len(stages)!=2 or [s["adapter"] for s in stages]!=
                ["maf-harness","openai-agents"] or
                stages[0]["attempt_id"]==stages[1]["attempt_id"]):
            raise ValueError("C09 must compare two real Agent Runtime SDKs")
        verified=[]
        for stage in stages:
            output=await workflow.execute_activity(
                "c09_real_agent_runtime",request|{"stage":stage},
                start_to_close_timeout=timedelta(seconds=95),
                retry_policy=RetryPolicy(maximum_attempts=1))
            result=await workflow.execute_activity(
                "c09_independent_verify",
                {"run_id":request["run_id"],"stage":stage,"model_result":output},
                start_to_close_timeout=timedelta(seconds=12),
                retry_policy=RetryPolicy(maximum_attempts=1))
            verified.append(result)
            if not result["passed"]:
                failed=await workflow.execute_activity(
                    "c09_finalize_platform_run",{"run_id":request["run_id"],"failed":True},
                    start_to_close_timeout=timedelta(seconds=12),
                    retry_policy=RetryPolicy(maximum_attempts=1))
                return {"run_id":request["run_id"],"state":failed["state"],
                        "runtime_swap_verified":False,"attempts":verified}
        finish=await workflow.execute_activity(
            "c09_finalize_platform_run",{"run_id":request["run_id"]},
            start_to_close_timeout=timedelta(seconds=12),
            retry_policy=RetryPolicy(maximum_attempts=1))
        return {"run_id":request["run_id"],"state":finish["state"],
                "runtime_swap_verified":True,"attempts":verified}
