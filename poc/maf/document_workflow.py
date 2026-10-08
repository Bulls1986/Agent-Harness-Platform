"""A11/A12 bounded MAF Workflow + *real trusted document fixture verifier*.

Only repository-owned fixture paths are accessible. No model, shell, arbitrary
code execution, OSS upload or production durable workflow is claimed.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Literal

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler
from verify_fixture import ROOT, verify_document
from workflow_probe import PlatformOutcome, TerminalDecisionExecutor, VerificationFact


@dataclass(frozen=True)
class DocumentRequest:
    fact: VerificationFact
    candidate: Literal["expected", "buggy"]


class IndependentDocumentVerifier(Executor):
    @handler
    async def verify(
        self, request: DocumentRequest, ctx: WorkflowContext[VerificationFact]
    ) -> None:
        if request.candidate not in ("expected", "buggy"):
            raise ValueError("Only trusted repository fixture candidates are allowed")
        result = verify_document(ROOT / "document" / request.candidate)
        # POC-local proof URI. A15 must replace it with a true OSS-backed Evidence.
        # Verification is a deterministic code action, not agent-generated text.
        evidence_ref = f"poc-fixture://document/{request.candidate}/summary.json"
        await ctx.send_message(
            VerificationFact(
                run_id=request.fact.run_id,
                plan_id=request.fact.plan_id,
                step_id=request.fact.step_id,
                attempt_id=request.fact.attempt_id,
                plan_version=request.fact.plan_version,
                passed=result["passed"],
                evidence_ref=evidence_ref,
            )
        )


def build_document_workflow():
    verifier = IndependentDocumentVerifier(id="trusted-document-verifier")
    decision = TerminalDecisionExecutor(id="platform-terminal-decision")
    return (
        WorkflowBuilder(name="poc-document-verification-gate", start_executor=verifier)
        .add_edge(verifier, decision)
        .build()
    )


async def run_document_case(
    candidate: Literal["expected", "buggy"],
    fact: VerificationFact | None = None,
) -> PlatformOutcome:
    request = DocumentRequest(
        fact=fact or VerificationFact.example(passed=False, evidence_ref=None),
        candidate=candidate,
    )
    result = await build_document_workflow().run(request)
    outcomes = result.get_outputs()
    if len(outcomes) != 1 or not isinstance(outcomes[0], PlatformOutcome):
        raise RuntimeError("Native MAF Workflow returned invalid terminal outcome")
    return outcomes[0]


async def _main() -> int:
    good = await run_document_case("expected")
    broken = await run_document_case("buggy")
    print(
        json.dumps(
            {
                "real_maf_workflow": True,
                "independent_verifier": True,
                "good": good.run_state,
                "broken": broken.run_state,
                "oss_evidence_verified": False,
                "task_persistence_verified": False,
            },
            sort_keys=True,
        )
    )
    return 0 if (good.run_state, broken.run_state) == ("COMPLETED", "FAILED") else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
