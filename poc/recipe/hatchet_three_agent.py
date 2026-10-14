"""M6 native three Agent SDK Recipe smoke, with native Hatchet durable Approval wait.

Synthetic task & external PG fixture only. Do NOT treat synthetic Artifact
locators, external ledger entries or local SDK models as production resources.
This module uses Hatchet as the ONLY technical scheduler and canonical
Harness PG as the ONLY Run/Step/Attempt business state authority.
"""
from __future__ import annotations

import argparse
import ast
import asyncio
from datetime import timedelta
import json
import os
import threading
import time
import traceback
from uuid import uuid4

from hatchet_sdk import (
    ClientConfig, Context, DurableContext, EmbeddedHatchetConfig, Hatchet,
)
from pydantic import BaseModel, ConfigDict, Field

from poc.closed_loop.external_ledger_demo import ExternalLedger
from poc.closed_loop.facts import PgFacts
from poc.closed_loop.real_model import (
    ModelConfiguration, ReviewOutcome, make_pydantic_agent, parse_requirements,
    parse_review,
)
from poc.closed_loop.tool_receipt import ToolReceiptJournal
from poc.recipe.gates import ArtifactRef, RecipeBlocked, RecipeGate
from poc.recipe.synthetic_artifacts import SyntheticArtifactFixture
from poc.runtime_spi.adapters import PydanticRuntimeAdapter, OpenAIAgentsRuntimeAdapter
from poc.runtime_spi.contract import AgentRuntimeDispatcher, ExecutionContext, RunRequest


class Input(BaseModel):
    run_id: str
    prompt: str
    scope: str = "project-synthetic"


class CodingDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    code: str = Field(min_length=20, max_length=32000)
    summary: str = Field(min_length=3, max_length=1000)


_cfg = ModelConfiguration.from_env()
_hatchet = Hatchet.from_embedded(
    ClientConfig(embedded=EmbeddedHatchetConfig(
        database_url=os.environ["HATCHET_POC_DATABASE_URL"],
        run_migrations=os.getenv("HARNESS_M6_WORKER_ROLE") is None,
    ))
)
workflow = _hatchet.workflow(
    name="harness-m6-three-agent-live-v1" if _cfg.mode == "live"
         else "harness-m6-three-agent-synthetic-sdk-v1",
    input_validator=Input,
)
FROZEN_RECIPE = {"version": "m6-three-agent-v1", "steps": [
    {"name": "plan", "runtime": "pydantic", "effect": "PURE"},
    {"name": "code", "runtime": "openai", "effect": "WRITE"},
    {"name": "verify", "runtime": "pydantic", "effect": "PURE"},
]}
APPROVAL_EVENT = "harness-m6-approval-decided-v1"
INPUT_EVENT = "harness-m6-input-submitted-v1"

PLAN_LOCAL = json.dumps({
    "feature": "Python two-number addition",
    "summary": "Write a small function add(a,b) that returns the sum of two integers.",
    "capabilities": ["Return the sum of two integers"],
    "business_rules": ["Do not execute untrusted code or install dependencies"],
    "acceptance_criteria": ["add(2,3) == 5", "add(-1,1) == 0"],
}, ensure_ascii=False)
CODE_LOCAL = json.dumps({
    "code": "def add(a: int, b: int) -> int:\n    return a + b\n",
    "summary": "Implements integer addition without dependencies.",
}, ensure_ascii=False)
VERIFY_LOCAL = json.dumps({
    "decision": "PASS", "summary": "Verified syntax and the addition function.",
    "issues": [], "risks": [], "recommendations": [],
}, ensure_ascii=False)
CODE_INSTRUCTIONS = (
    "You are the Coding Agent. The input is a verified JSON specification "
    "for a simple Python two-integer addition function. Return ONLY strict "
    "JSON with exactly two string fields: code (valid Python source containing "
    "def add(a,b) and returning a+b), and summary (one sentence). Do not use "
    "Markdown or backticks. Do not ask to run shell or install modules."
)
VERIFY_INSTRUCTIONS = (
    "You are an independent software verification Agent, NOT the Coding Agent. "
    "Review the provided Python code JSON and the original requirements. "
    "Return ONLY strict JSON fields decision ('PASS' or 'NEEDS_WORK'), summary, "
    "issues [], risks [], recommendations []; no markdown. PASS only if code "
    "defines add(a,b) and computes a+b, otherwise NEEDS_WORK. "
    "Never claim it was actually executed."
)


def gate() -> RecipeGate:
    return RecipeGate(os.environ["HARNESS_POC_DATABASE_URL"])


def fixtures() -> SyntheticArtifactFixture:
    return SyntheticArtifactFixture(os.environ["HARNESS_LEDGER_DATABASE_URL"])


async def await_binding(rid: str, native_id: str):
    for _ in range(120):
        with PgFacts().tx() as c:
            row = c.execute(
                "SELECT provider_workflow_id,state,plan_version "
                "FROM harness_run WHERE id=%s", (rid,)).fetchone()
        if row == (native_id, "RUNNING", 1):
            return
        await asyncio.sleep(0.25)
    raise RecipeBlocked("M6 native Hatchet Provider was not bound to Harness Run")


def context(rid: str, name: str) -> ExecutionContext:
    return ExecutionContext(
        run_id=rid, turn_id=rid+":turn", session_id=rid+":session",
        isolation_scope="project-synthetic",
        execution_id=rid+":"+name, owner_id="m6-native-hatchet-worker",
        fencing_token=1,
    )


def make_local_pydantic(payload: str):
    from pydantic_ai import Agent
    from pydantic_ai.messages import ModelResponse, TextPart
    from pydantic_ai.models.function import FunctionModel

    def respond(messages, info):
        return ModelResponse(parts=[TextPart(payload)])

    return Agent(FunctionModel(respond))


def make_live_pydantic(instructions: str):
    from openai import AsyncOpenAI
    from pydantic_ai import Agent
    from pydantic_ai.models.openai import OpenAIResponsesModel
    from pydantic_ai.providers.openai import OpenAIProvider
    client = AsyncOpenAI(base_url=_cfg.base_url,api_key=_cfg.api_key,
                         timeout=150.0,max_retries=0)
    model = OpenAIResponsesModel(
        _cfg.model_id, provider=OpenAIProvider(openai_client=client))
    return Agent(model,instructions=instructions)


def make_coding_agent():
    from agents import Agent, set_tracing_disabled
    set_tracing_disabled(True)
    if _cfg.mode == "live":
        from agents.models.openai_responses import OpenAIResponsesModel
        from openai import AsyncOpenAI
        return Agent(
            name="m6-code", instructions=CODE_INSTRUCTIONS,
            model=OpenAIResponsesModel(
                model=_cfg.model_id,openai_client=AsyncOpenAI(
                    base_url=_cfg.base_url,api_key=_cfg.api_key,
                    timeout=150.0,max_retries=0)))
    from agents.models.interface import Model, ModelResponse
    from agents.usage import Usage
    from openai.types.responses import ResponseOutputMessage, ResponseOutputText

    class LocalModel(Model):
        async def get_response(self, *args, **kwargs):
            return ModelResponse(
                output=[ResponseOutputMessage(
                    id="m6-synthetic-code",role="assistant",type="message",
                    status="completed",content=[ResponseOutputText(
                        annotations=[],text=CODE_LOCAL,type="output_text")])],
                usage=Usage(requests=1),response_id="m6-synthetic-responses")

        async def stream_response(self, *args, **kwargs):
            if False:
                yield None
            raise NotImplementedError("M6 bounded test uses completed SDK response")

    return Agent(name="m6-code",instructions=CODE_INSTRUCTIONS,model=LocalModel())


async def invoke(rid: str, step: str, adapter, text: str) -> str:
    request = RunRequest(
        context(rid, step), adapter.name, text,
        capabilities=frozenset({"model"}))
    events = await AgentRuntimeDispatcher(adapter).execute(request)
    if not events or events[-1].type != "run.completed":
        raise RecipeBlocked("Real SDK did not produce a completed model result")
    output = events[-1].data.get("result")
    if not isinstance(output,str) or not output:
        raise RecipeBlocked("SDK output missing")
    return output


def _checked_ref(value: dict, scope: str) -> ArtifactRef:
    artifact=ArtifactRef(value["ref"],value["digest"],scope)
    artifact.validate(scope)
    return artifact


def _verified(g: RecipeGate, rid: str, step: str,
              attempt: str, content: bytes, scope: str) -> dict:
    store=fixtures()
    ref=store.put(rid,step,content,scope=scope)
    actual=store.verified_bytes(ref)
    if actual!=content:
        raise RecipeBlocked("Independent fixture byte read mismatch")
    # In production an authenticated independent OSS Verifier must produce
    # this reference. A local fixture hash is deliberately NOT that proof.
    g.verify_step(rid,step,attempt,ref,"synthetic-fixture:"+ref.digest)
    return {"ref":ref.ref,"digest":ref.digest}


@workflow.task(execution_timeout=timedelta(minutes=4),retries=0)
async def plan_step(input: Input,ctx: Context) -> dict:
    await await_binding(input.run_id,ctx.workflow_run_id)
    g=gate()
    attempt=input.run_id+"-plan-a1"
    g.claim_step(input.run_id,"plan",attempt)
    agent=(make_pydantic_agent(_cfg) if _cfg.mode=="live"
           else make_local_pydantic(PLAN_LOCAL))
    result=await invoke(input.run_id,"plan",PydanticRuntimeAdapter(agent),input.prompt)
    draft=parse_requirements(result)
    return _verified(g,input.run_id,"plan",attempt,
                     draft.model_dump_json().encode(),input.scope)


@workflow.durable_task(parents=[plan_step],
                       execution_timeout=timedelta(minutes=7),retries=0)
async def await_input(input: Input,ctx: DurableContext) -> dict:
    parent=_checked_ref(ctx.task_output(plan_step),input.scope)
    # Existing plan must already be independently verified.
    fixtures().verified_bytes(parent)
    g=gate()
    g.request_input(input.run_id,"m6-synthetic-input-requester",parent.digest)
    current=g.snapshot(input.run_id)
    if current["state"]=="WAITING_INPUT":
        await ctx.aio_wait_for_event(
            INPUT_EVENT, f"input.run_id == '{input.run_id}'",
            scope=input.run_id,lookback_window=timedelta(minutes=8),
            label="M6 verified external input",
        )
    # On Native Worker replay, the same Run may already be RESOLVED.
    # Never create a second User Request or lose its durable resolution.
    state=g.snapshot(input.run_id)
    answers=state["inputs"]
    if (state["state"]!="RUNNING" or len(answers)!=1
            or answers[0]["state"]!="RESOLVED"):
        raise RecipeBlocked("Original Run did not receive verified input")
    answer=_checked_ref({
        "ref":answers[0]["response_ref"],
        "digest":answers[0]["response_digest"],
    },input.scope)
    fixtures().verified_bytes(answer)
    return {"input_ref":answer.ref, "plan_ref":parent.ref}


@workflow.durable_task(parents=[await_input],
                       execution_timeout=timedelta(minutes=7),retries=0)
async def await_approval(input: Input,ctx: DurableContext) -> dict:
    parent=_checked_ref(ctx.task_output(plan_step),input.scope)
    if fixtures().verified_bytes(parent) is None:
        raise RecipeBlocked("No verified Plan bytes")
    g=gate()
    g.request_approval(input.run_id,"code","m6-synthetic-requester",parent.digest)
    # Hatchet owns technical waits; business approval remains in Harness PG.
    if g.snapshot(input.run_id)["state"]=="WAITING_APPROVAL":
        await ctx.aio_wait_for_event(
            APPROVAL_EVENT, f"input.run_id == '{input.run_id}'",
            scope=input.run_id, lookback_window=timedelta(minutes=8),
            label="M6 external approval decision",
        )
    # If Worker A died after approval, B reuses the SAME approval and Run.
    snap=g.snapshot(input.run_id)
    approved=[a for a in snap["approvals"] if a["step"]=="code"]
    if (snap["state"]!="RUNNING" or len(approved)!=1
            or approved[0]["decision"]!="APPROVED"):
        raise RecipeBlocked("Authoritative Harness approval not granted")
    return {"approved":True,"plan_ref":parent.ref}


@workflow.task(parents=[await_approval],
               execution_timeout=timedelta(minutes=4),retries=0)
async def code_step(input: Input,ctx: Context) -> dict:
    g=gate()
    attempt=input.run_id+"-code-a1"
    parent=g.claim_step(input.run_id,"code",attempt)
    if parent is None:
        raise RecipeBlocked("No verified typed Plan parent")
    plan_bytes=fixtures().verified_bytes(parent)
    parse_requirements(plan_bytes.decode())
    g.require_write_permit(input.run_id,"code",attempt)
    answers=g.snapshot(input.run_id)["inputs"]
    if len(answers)!=1 or answers[0]["state"]!="RESOLVED":
        raise RecipeBlocked("Required input not durably resolved")
    answer=ArtifactRef(answers[0]["response_ref"],
                       answers[0]["response_digest"],input.scope)
    input_bytes=fixtures().verified_bytes(answer)
    if len(input_bytes)>4096:
        raise RecipeBlocked("Input exceeds bounded M6 synthetic task")
    agent=make_coding_agent()
    prompt=json.dumps({"requirements":parse_requirements(plan_bytes.decode()).model_dump(),
                       "provided_input":input_bytes.decode()},ensure_ascii=False)
    result=await invoke(input.run_id,"code",OpenAIAgentsRuntimeAdapter(agent),
                        prompt)
    draft=CodingDraft.model_validate(json.loads(result))
    source=ast.parse(draft.code)
    if not any(isinstance(n,ast.FunctionDef) and n.name=="add"
               for n in source.body):
        raise RecipeBlocked("Coding Agent omitted frozen function contract")

    # Actual *separate database* non-idempotent synthetic effect, recorded
    # via the already-existing M4 ReceiptJournal. No file/shell host Tool.
    db=PgFacts()
    journal=ToolReceiptJournal(db)
    ledger=ExternalLedger(os.environ["HARNESS_LEDGER_DATABASE_URL"])
    eid=input.run_id+"-synthetic-effect"
    owner="m6-native-hatchet-worker"
    journal.register_intent(
        input.run_id,1,"code",attempt,eid,owner,1,
        "synthetic.code.persist","m6-synthetic-target",
        input.run_id+":external-effect")
    journal.dispatch(eid,owner,1)
    ledger.debit(eid,"synthetic.code.persist","m6-synthetic-target",
                 input.run_id+":external-effect")
    journal.mark_unknown(eid,"LOST_ACK")
    journal.reconcile(eid,ledger.find)
    return _verified(g,input.run_id,"code",attempt,
                     draft.model_dump_json().encode(),input.scope)


@workflow.task(parents=[code_step],
               execution_timeout=timedelta(minutes=4),retries=0)
async def verify_step(input: Input,ctx: Context) -> dict:
    g=gate()
    attempt=input.run_id+"-verify-a1"
    parent=g.claim_step(input.run_id,"verify",attempt)
    if parent is None:
        raise RecipeBlocked("No verified code ArtifactRef")
    stored=CodingDraft.model_validate(json.loads(fixtures().verified_bytes(parent)))
    if not any(isinstance(n,ast.FunctionDef) and n.name=="add"
               for n in ast.parse(stored.code).body):
        raise RecipeBlocked("Code Artifact fails independent AST check")
    agent=(make_live_pydantic(VERIFY_INSTRUCTIONS) if _cfg.mode=="live"
           else make_local_pydantic(VERIFY_LOCAL))
    original=g.snapshot(input.run_id)["steps"][0]
    plan_ref=ArtifactRef(
        original["output_ref"],original["output_digest"],input.scope)
    verified_plan=parse_requirements(fixtures().verified_bytes(plan_ref).decode())
    result=await invoke(
        input.run_id,"verify",PydanticRuntimeAdapter(agent),
        json.dumps({"requirements": verified_plan.model_dump(),
                    "code": stored.model_dump()},ensure_ascii=False))
    review=parse_review(result)
    if review.decision!="PASS":
        raise RecipeBlocked("Independent verification rejected Coding Artifact")
    answer=_verified(g,input.run_id,"verify",attempt,
                     review.model_dump_json().encode(),input.scope)
    answer["decision"]=review.decision
    return answer


def execute(*,rid: str,decision: str) -> dict:
    g=gate()
    g.freeze(rid,FROZEN_RECIPE,scope="project-synthetic",
             principal="m6-synthetic-operator")
    command=rid+":segment-0:create:v1"
    db=PgFacts()
    db.dispatch(command)
    try:
        ref=workflow.run(Input(run_id=rid,prompt=(
            "Build a Python function add(a,b) that returns the sum of two "
            "integers. Produce precise requirements and verify that code "
            "contains the function and implements addition.")),
            wait_for_result=False)
    except Exception:
        db.unknown(command)
        raise
    db.bind(command,ref.workflow_run_id)

    operator: dict={"event_published":False,"input_published":False}
    def decision_from_independent_actor():
        try:
            for _ in range(240):
                snap=g.snapshot(rid)
                if snap["state"]=="WAITING_INPUT" and not operator["input_published"]:
                    answer=fixtures().put(
                        rid,"input",b"Confirmed synthetic input: two integers.",
                        scope="project-synthetic")
                    if not fixtures().verified_bytes(answer):
                        raise AssertionError("External input fixture not verified")
                    g.answer_input(
                        rid,"m6-independent-input-operator",answer,
                        "synthetic-fixture:"+answer.digest)
                    _hatchet.event.push(INPUT_EVENT,{"run_id":rid},scope=rid)
                    operator["input_published"]=True
                if snap["state"]=="WAITING_APPROVAL":
                    if snap["steps"][1]["state"]!="PENDING":
                        raise AssertionError("Code began before approval")
                    with db.tx() as c:
                        effects=c.execute(
                            "SELECT count(*) FROM harness_tool_intent WHERE run_id=%s",
                            (rid,)).fetchone()[0]
                    if effects:
                        raise AssertionError("Tool dispatched before approval")
                    # The independent operator's decision is committed to
                    # Harness PG FIRST; Hatchet event only wakes the execution.
                    g.decide_approval(
                        rid,"code","m6-independent-approver",decision)
                    _hatchet.event.push(APPROVAL_EVENT,
                                        {"run_id":rid,"decision":decision},
                                        scope=rid)
                    operator["event_published"]=True
                    return
                time.sleep(.25)
            raise TimeoutError("Durable approval state never appeared")
        except Exception as exc:
            operator["error"]=repr(exc)
    thread=threading.Thread(target=decision_from_independent_actor,daemon=True)
    thread.start()

    provider_error=None
    try:
        _hatchet.runs.get_run_ref(ref.workflow_run_id).result()
    except Exception as exc:
        provider_error=type(exc).__name__
    thread.join(3)
    if operator.get("error"):
        raise RuntimeError("External approval operator failed: "+operator["error"])
    if not operator.get("input_published") or not operator.get("event_published"):
        raise RuntimeError("Missing durable input or approval event")
    state=g.snapshot(rid)
    ledger=ExternalLedger(os.environ["HARNESS_LEDGER_DATABASE_URL"])
    effect_count=len(ledger.find(rid+"-synthetic-effect"))
    if decision=="REJECTED":
        if (state["state"]!="BLOCKED" or effect_count!=0
                or state["steps"][1]["state"]!="PENDING"):
            raise AssertionError("Rejected approval incorrectly executed Code")
        return {"outcome":"REJECTION_PASS","run_id":rid,
                "native_provider_id":ref.workflow_run_id,
                "no_external_effect":True,"state":state["state"]}
    if provider_error:
        raise RuntimeError("Native Hatchet three-Agent execution failed: "+provider_error)
    if (state["state"]!="COMPLETED" or
            any(x["state"]!="VERIFIED" for x in state["steps"])
            or effect_count!=1):
        raise AssertionError("Domain/Receipt/Verifier/Effect final invariant failed")
    return {
        "outcome":"PASS",
        "runtime":"REAL_HATCHET_EMBEDDED_DOCKER_PG",
        "sdk_types":"PYDANTIC_AI_OPENAI_AGENTS_PYDANTIC_AI",
        "model_mode":_cfg.mode,"model_id":_cfg.model_id,
        "domain_run_id":rid,"native_provider_id":ref.workflow_run_id,
        "domain_step_states":[x["state"] for x in state["steps"]],
        "receipt":"CONFIRMED_SUCCESS_REAL_INDEPENDENT_FIXTURE_PG",
        "external_nonidempotent_effects":effect_count,
        "durable_approval":"NATIVE_EVENT",
        "durable_input":"NATIVE_EVENT_SAME_RUN",
        "artifact_storage":"REAL_EXTERNAL_PG_FIXTURE_NOT_OSS",
        "cube_guest":"NOT_TESTED", "worker_kill_resume":"NOT_TESTED",
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--decision",choices=("APPROVED","REJECTED"),
                        default="APPROVED")
    parser.add_argument("--run-id")
    parser.add_argument("--worker-only",action="store_true")
    args=parser.parse_args()
    if args.worker_only:
        if os.getenv("HARNESS_M6_WORKER_ROLE") not in ("worker-A","worker-B"):
            raise RuntimeError("Worker role must be an explicit isolated test role")
        _hatchet.worker(
            "harness-m6-resume-"+os.environ["HARNESS_M6_WORKER_ROLE"],
            workflows=[workflow]).start()
        return
    rid=args.run_id or "m6native-"+uuid4().hex
    worker=_hatchet.worker("harness-m6-cross-sdk-worker",workflows=[workflow])
    threading.Thread(target=worker.start,daemon=True).start()
    time.sleep(5)
    status=0
    try:
        print(json.dumps(execute(rid=rid,decision=args.decision),
                         sort_keys=True,ensure_ascii=False),flush=True)
    except Exception:
        status=1
        traceback.print_exc()
    finally:
        _hatchet.stop_embedded()
        import sys
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(status)


if __name__=="__main__":
    main()