"""A11 narrow native MAF Workflow probe: platform-owned identifiers & terminal status.

This tests WorkflowBuilder/Executor (actual MAF execution), NOT a full
Plan→Execute→Verify→Replan implementation or durable/task-fact persistence.
The only success signal is a *trusted* external verification fact with evidence.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Never
from uuid import uuid4

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler


@dataclass(frozen=True)
class VerificationFact:
    run_id: str
    plan_id: str
    step_id: str
    attempt_id: str
    plan_version: int
    passed: bool
    evidence_ref: str | None

    @classmethod
    def example(cls, *, passed: bool, evidence_ref: str | None) -> "VerificationFact":
        # Platform IDs are generated outside MAF and never taken from its session.
        return cls(
            run_id=f"run-{uuid4().hex}",
            plan_id=f"plan-{uuid4().hex}",
            step_id=f"step-{uuid4().hex}",
            attempt_id=f"attempt-{uuid4().hex}",
            plan_version=1,
            passed=passed,
            evidence_ref=evidence_ref,
        )


@dataclass(frozen=True)
class PlatformOutcome:
    run_id: str
    plan_id: str
    step_id: str
    attempt_id: str
    plan_version: int
    run_state: str
    verification_state: str
    evidence_ref: str | None


class FactRoutingExecutor(Executor):
    @handler
    async def accept(
        self, fact: VerificationFact, ctx: WorkflowContext[VerificationFact]
    ) -> None:
        if not all((fact.run_id, fact.plan_id, fact.step_id, fact.attempt_id)):
            raise ValueError("Missing platform-owned execution identity")
        if fact.plan_version < 1:
            raise ValueError("Plan must be versioned")
        await ctx.send_message(fact)


class TerminalDecisionExecutor(Executor):
    @handler
    async def decide(
        self, fact: VerificationFact, ctx: WorkflowContext[Never, PlatformOutcome]
    ) -> None:
        # Never allow the agent's narrative or a bare passed=True to close a Run.
        success = fact.passed and bool(fact.evidence_ref)
        result = PlatformOutcome(
            run_id=fact.run_id,
            plan_id=fact.plan_id,
            step_id=fact.step_id,
            attempt_id=fact.attempt_id,
            plan_version=fact.plan_version,
            run_state="COMPLETED" if success else "FAILED",
            verification_state="SUCCEEDED" if success else "VERIFICATION_FAILURE",
            evidence_ref=fact.evidence_ref,
        )
        await ctx.yield_output(result)


def build_workflow():
    accept = FactRoutingExecutor(id="platform-fact-intake")
    decide = TerminalDecisionExecutor(id="platform-terminal-decision")
    return (
        WorkflowBuilder(name="poc-platform-terminal-gate", start_executor=accept)
        .add_edge(accept, decide)
        .build()
    )


async def execute_fact(fact: VerificationFact) -> PlatformOutcome:
    result = await build_workflow().run(fact)
    outputs = result.get_outputs()
    if len(outputs) != 1 or not isinstance(outputs[0], PlatformOutcome):
        raise RuntimeError("MAF Workflow did not return exactly one platform outcome")
    return outputs[0]


async def _main() -> int:
    # This is trusted data for testing the state boundary, not a model-written verdict.
    good = await execute_fact(
        VerificationFact.example(passed=True, evidence_ref="evidence://poc/verified")
    )
    bad = await execute_fact(
        VerificationFact.example(passed=False, evidence_ref="evidence://poc/failed")
    )
    print(json.dumps({"pass_case":good.run_state, "failure_case":bad.run_state,
                      "workflow_executed":True, "task_recovery_verified":False}))
    return 0 if (good.run_state, bad.run_state) == ("COMPLETED", "FAILED") else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
