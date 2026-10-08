"""Incompatible v2 with same Workflow Type; offline Replayer test only."""
from __future__ import annotations
from datetime import timedelta
from temporalio import workflow

@workflow.defn(name="poc-c-document-review")
class IncompatibleDocumentReviewWorkflow:
    @workflow.run
    async def run(self, request: dict) -> dict:
        # V1 schedules an Activity as its first command, not a Timer.
        await workflow.sleep(timedelta(seconds=3))
        return {"state": "INCOMPATIBLE_V2_SHOULD_NOT_REPLAY"}
