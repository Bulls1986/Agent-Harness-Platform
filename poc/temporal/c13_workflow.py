"""C13 deterministic Workflow only. All OTel/PG Activity code stays external."""
from __future__ import annotations
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

@workflow.defn(name="poc-c13-native-observability")
class ObservedRuntimeWorkflow:
    @workflow.run
    async def run(self,request:dict)->dict:
        outcomes=[]
        for stage in request["stages"]:
            outcome=await workflow.execute_activity(
                "c13_bounded_harness_activity",request|{"stage":stage},
                start_to_close_timeout=timedelta(seconds=15),
                retry_policy=RetryPolicy(maximum_attempts=1))
            outcomes.append(outcome)
        await workflow.execute_activity(
            "c13_bounded_harness_finalize",{"run_id":request["run_id"]},
            start_to_close_timeout=timedelta(seconds=15))
        return {"state":"COMPLETED","activities":outcomes}
