"""C15: Temporal-native deterministic Workflow, no model/PG/SSE logic."""
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

@workflow.defn(name="poc-c15-g3-streaming")
class LiveStreamWorkflow:
    @workflow.run
    async def run(self,request:dict):
        produced=await workflow.execute_activity(
            "c15_stream_model",request,
            start_to_close_timeout=timedelta(seconds=160),
            retry_policy=RetryPolicy(maximum_attempts=1))
        if produced["cancelled"]:
            return {"state":"CANCELLED"}
        if request.get("save_artifact",False):
            artifact=await workflow.execute_activity(
                "c15_write_s3_artifact",
                request|{"digest":produced["digest"],"count":produced["count"]},
                start_to_close_timeout=timedelta(seconds=55),
                retry_policy=RetryPolicy(maximum_attempts=1))
            if artifact["cancelled"]:
                return {"state":"CANCELLED"}
            proof=await workflow.execute_activity(
                "c15_verify_s3_artifact",request|artifact,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=1))
            if not proof["passed"]:
                return {"state":"CANCELLED"}
        verified=await workflow.execute_activity(
            "c15_verify_tokens",request|{"digest":produced["digest"],"count":produced["count"]},
            start_to_close_timeout=timedelta(seconds=15),
            retry_policy=RetryPolicy(maximum_attempts=1))
        if not verified["passed"]:
            return {"state":"CANCELLED"}
        return await workflow.execute_activity(
            "c15_finish",request,
            start_to_close_timeout=timedelta(seconds=15),
            retry_policy=RetryPolicy(maximum_attempts=1))