"""C06 deterministic Temporal Workflow: only schedules Tool Activity retry.

No imports of PostgreSQL/HTTP/OS/Worker code: those belong to Activity.
"""
from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy


@workflow.defn(name="poc-c06-nonretryable-dispatch")
class GuardedNonRetryableWorkflow:
    @workflow.run
    async def run(self, request: dict) -> dict:
        pure=await workflow.execute_activity(
            "c06_pure_retry_probe",{"kind":"PURE"},
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(maximum_attempts=2,
                                     initial_interval=timedelta(seconds=1)))
        if pure["outcome"]!="PURE_RECOVERED":
            raise ValueError("PURE infrastructure retry did not recover")
        outcome=await workflow.execute_activity(
            "c06_guarded_nonretryable_tool",request,
            start_to_close_timeout=timedelta(seconds=9),
            retry_policy=RetryPolicy(maximum_attempts=2,
                                     initial_interval=timedelta(seconds=1)))
        return {"run_id":request["binding"]["run_id"],
                "native_workflow_id":request["binding"]["native_workflow_id"],
                "attempt_id":request["binding"]["attempt_id"],
                "pure_retry_attempt":pure["activity_attempt"],**outcome}
