"""POC-C Activity/Data Plane fixture adapters.

Reuses exactly the same independent Document fixture verifier as POC-A.
Temporal Workflow itself does not call an LLM, access a file or run shell.
These reference adapters do NOT count as a real Model/Sandbox swap.
"""
from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity

MAF_POC = Path(__file__).resolve().parents[1] / "maf"
if str(MAF_POC) not in sys.path:
    sys.path.insert(0, str(MAF_POC))
from verify_fixture import ROOT, verify_document


class FixtureAgentA:
    name = "fixture-a"

    def execute(self, candidate: str) -> str:
        if candidate != "buggy":
            raise ValueError("Fixture A is strictly the known-broken input")
        return "poc-fixture://document/buggy/summary.json"


class FixtureAgentB:
    name = "fixture-b"

    def execute(self, candidate: str) -> str:
        if candidate != "expected":
            raise ValueError("Fixture B is strictly the known-good input")
        return "poc-fixture://document/expected/summary.json"


ADAPTERS = {x.name: x for x in (FixtureAgentA(), FixtureAgentB())}


@activity.defn(name="fixture_agent_execute")
async def fixture_agent_execute(request: dict) -> dict:
    name = request.get("adapter")
    candidate = request.get("candidate")
    if name not in ADAPTERS:
        raise ValueError("Unknown fixture runtime adapter")
    ref = ADAPTERS[name].execute(candidate)
    return {"run_id":request["run_id"],"attempt_id":request["attempt_id"],
            "adapter":name,"candidate":candidate,"artifact_ref":ref}


@activity.defn(name="independent_document_verify")
async def independent_document_verify(output: dict) -> dict:
    if output.get("candidate") not in ("buggy", "expected"):
        raise ValueError("Candidate is not in the trusted verifier allowlist")
    candidate = output["candidate"]
    expected_ref=f"poc-fixture://document/{candidate}/summary.json"
    if output.get("artifact_ref") != expected_ref:
        raise ValueError("Artifact reference mismatch")
    verified=verify_document(ROOT / "document" / candidate)
    return {"run_id":output["run_id"],"attempt_id":output["attempt_id"],
            "passed":bool(verified["passed"]),"evidence_ref":expected_ref}
