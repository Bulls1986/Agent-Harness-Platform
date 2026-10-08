"""POC-C native Temporal Workflow: deterministic control plane only.

Workflow code contains no LLM, HTTP, DB, file, git, shell or clock calls.
Platform Run/Plan/Step/Attempt identifiers are caller-owned; Temporal Workflow
ID is a separate opaque native runtime binding. The Agent and independent
Verifier are Activities; their fixture implementations are not real models.
"""
from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy


@workflow.defn(name="poc-c-document-review")
class DocumentReviewWorkflow:
    def __init__(self) -> None:
        self.phase = "CREATED"
        self.approval: str | None = None
        self.replan_version = 1
        self.attempts: list[dict] = []

    @workflow.signal
    def decide(self, decision: str) -> None:
        if decision not in ("APPROVED", "REJECTED"):
            raise ValueError("Unsupported approval decision")
        if self.phase == "WAITING_APPROVAL" and self.approval is None:
            self.approval = decision

    @workflow.query
    def snapshot(self) -> dict:
        return {
            "phase": self.phase,
            "plan_version": self.replan_version,
            "approval": self.approval,
            "attempts": list(self.attempts),
        }

    @workflow.run
    async def run(self, request: dict) -> dict:
        if set(request) != {"run_id", "attempt_ids"}:
            raise ValueError("Invalid platform workflow request shape")
        if not isinstance(request["run_id"], str) or not request["run_id"].startswith("run-"):
            raise ValueError("Platform-owned Run ID required")
        attempts = request["attempt_ids"]
        if (not isinstance(attempts, list) or len(attempts) != 2 or
                any(not isinstance(a, str) or not a.startswith("attempt-") for a in attempts) or
                attempts[0] == attempts[1]):
            raise ValueError("Two different platform Attempt IDs required")

        # v1: deterministic fixture produces broken candidate. Only Activities
        # may generate artifacts or invoke an actual runtime.
        self.phase = "VERIFY_V1"
        first = await workflow.execute_activity(
            "fixture_agent_execute",
            {"run_id":request["run_id"],"attempt_id":attempts[0],
             "adapter":"fixture-a","candidate":"buggy"},
            start_to_close_timeout=timedelta(seconds=12),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
        check = await workflow.execute_activity(
            "independent_document_verify",
            first, start_to_close_timeout=timedelta(seconds=12),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
        if check["passed"]:
            raise ValueError("Broken candidate incorrectly accepted")
        self.attempts.append({"attempt_id":attempts[0],"plan_version":1,
                              "verification":"FAILED","adapter":"fixture-a"})

        # Approval wait survives Temporal Worker process interruption; it
        # does not synthesize a new Harness Attempt while waiting.
        self.phase = "WAITING_APPROVAL"
        await workflow.wait_condition(lambda: self.approval is not None)
        if self.approval != "APPROVED":
            self.phase = "FAILED"
            return {"run_id":request["run_id"],"state":"FAILED",
                    "plan_version":1,"attempts":self.attempts,
                    "approval":"REJECTED","native_replay_possible":True}

        self.replan_version = 2
        self.phase = "VERIFY_V2"
        second = await workflow.execute_activity(
            "fixture_agent_execute",
            {"run_id":request["run_id"],"attempt_id":attempts[1],
             "adapter":"fixture-b","candidate":"expected"},
            start_to_close_timeout=timedelta(seconds=12),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
        verified = await workflow.execute_activity(
            "independent_document_verify",
            second, start_to_close_timeout=timedelta(seconds=12),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
        self.attempts.append({"attempt_id":attempts[1],"plan_version":2,
                              "verification":"PASSED" if verified["passed"] else "FAILED",
                              "adapter":"fixture-b"})
        self.phase = "COMPLETED" if verified["passed"] else "FAILED"
        return {
            "run_id":request["run_id"],"state":self.phase,
            "plan_version":self.replan_version,"attempts":self.attempts,
            "approval":"APPROVED","evidence_ref":verified["evidence_ref"],
            "native_replay_possible":True,
        }
