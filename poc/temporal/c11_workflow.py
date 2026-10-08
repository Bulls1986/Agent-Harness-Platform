"""C11 pure deterministic Temporal Workflow: SandboxProvider/Storage are Activities."""
from __future__ import annotations

from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy


@workflow.defn(name="poc-c11-sandbox-artifacts")
class SandboxArtifactWorkflow:
    @workflow.run
    async def run(self,request:dict)->dict:
        if (set(request)!={"run_id","native_workflow_id","frozen_workflow_version",
                          "frozen_image_digest","stages"} or
                len(request["stages"])!=2 or
                [s["provider"] for s in request["stages"]]!=
                ["docker-oneshot","docker-session"]):
            raise ValueError("C11 frozen sandbox/provider request invalid")
        artifacts=[]
        for stage in request["stages"]:
            info=await workflow.execute_activity(
                "c11_sandbox_to_objectstore",
                request|{"stage":stage},start_to_close_timeout=timedelta(seconds=90),
                retry_policy=RetryPolicy(maximum_attempts=1))
            check=await workflow.execute_activity(
                "c11_verify_s3_evidence",
                request|{"stage":stage,"artifact_id":info["artifact_id"]},
                start_to_close_timeout=timedelta(seconds=40),
                retry_policy=RetryPolicy(maximum_attempts=1))
            if not check["passed"]:
                raise ValueError("C11 independently verified Artifact failed")
            artifacts.append({"provider":stage["provider"],
                              "artifact_id":info["artifact_id"],
                              "evidence_id":check["evidence_id"]})
        await workflow.execute_activity(
            "c11_finalize_run",{"run_id":request["run_id"]},
            start_to_close_timeout=timedelta(seconds=12),
            retry_policy=RetryPolicy(maximum_attempts=1))
        return {"run_id":request["run_id"],"state":"COMPLETED",
                "artifact_refs_only":True,"artifacts":artifacts}
