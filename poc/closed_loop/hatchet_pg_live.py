"""Real Hatchet Embedded with external Docker PostgreSQL + two public Agent SDKs.

LIMITED POC: model-only PURE tasks, no Cube, no external Tool/Receipt,
no token-level streaming, no cross-worker failover in this one run.
"""
from __future__ import annotations

import argparse
import json
import os
import threading
import time
import traceback
from uuid import uuid4

from hatchet_sdk import ClientConfig, Context, EmbeddedHatchetConfig, Hatchet
from pydantic import BaseModel

from poc.closed_loop.facts import PgFacts
from poc.runtime_spi.contract import AgentRuntimeDispatcher, ExecutionContext, RunRequest

hatchet = Hatchet.from_embedded(
    ClientConfig(embedded=EmbeddedHatchetConfig(
        database_url=os.environ["HATCHET_POC_DATABASE_URL"],
        run_migrations=True,
    ))
)


class LoopInput(BaseModel):
    run_id: str
    prompt: str = "a safe model-only handoff"


workflow = hatchet.workflow(
    name="harness-pg-minimal-run-v1",
    input_validator=LoopInput,
)


def runtime_context(run_id: str, runtime: str) -> ExecutionContext:
    # Only for PURE no-Sandbox POC; actual trusted HC-03 admission is not yet tested.
    return ExecutionContext(
        run_id=run_id, turn_id=run_id + ":turn", session_id=run_id + ":session",
        isolation_scope="model-only-poc", execution_id=run_id + ":" + runtime,
        owner_id="hatchet-pg-demo-worker", fencing_token=1,
    )


@workflow.task()
async def pydantic_step(input: LoopInput, ctx: Context) -> dict[str, str]:
    from pydantic_ai import Agent
    from pydantic_ai.messages import ModelResponse, TextPart
    from pydantic_ai.models.function import FunctionModel
    from poc.runtime_spi.adapters import PydanticRuntimeAdapter

    db = PgFacts()
    cached = db.start_step(input.run_id, "pydantic", input.prompt)
    if cached is not None:
        return {"output": cached}

    def model(messages, info):
        return ModelResponse(parts=[TextPart("pydantic-sdk-real-run")])

    adapter = PydanticRuntimeAdapter(Agent(FunctionModel(model)))
    events = await AgentRuntimeDispatcher(adapter).execute(
        RunRequest(runtime_context(input.run_id, "pydantic"), "pydantic", input.prompt)
    )
    if events[-1].type != "run.completed":
        raise RuntimeError("Pydantic SDK Step did not complete")
    result = events[-1].data["result"]
    db.finish_step(input.run_id, "pydantic", result, events)
    return {"output": result}


@workflow.task(parents=[pydantic_step])
async def openai_step(input: LoopInput, ctx: Context) -> dict[str, str]:
    from agents import Agent
    from agents.models.interface import Model, ModelResponse
    from agents.usage import Usage
    from openai.types.responses import ResponseOutputMessage, ResponseOutputText
    from poc.runtime_spi.adapters import OpenAIAgentsRuntimeAdapter

    parent = ctx.task_output(pydantic_step)["output"]
    db = PgFacts()
    cached = db.start_step(input.run_id, "openai", parent)
    if cached is not None:
        return {"output": cached}

    class LocalModel(Model):
        async def get_response(self, *args, **kwargs):
            msg = ResponseOutputMessage(
                id="closed-loop", role="assistant", type="message", status="completed",
                content=[ResponseOutputText(
                    annotations=[], text="openai-sdk-real-run", type="output_text",
                )],
            )
            return ModelResponse(
                output=[msg], usage=Usage(requests=1),
                response_id="closed-loop-response",
            )

        async def stream_response(self, *args, **kwargs):
            if False:
                yield None
            raise NotImplementedError("Real Token SSE is not in this limited gate")

    adapter = OpenAIAgentsRuntimeAdapter(Agent(name="closed-loop", model=LocalModel()))
    events = await AgentRuntimeDispatcher(adapter).execute(
        RunRequest(runtime_context(input.run_id, "openai-agents"),
                   "openai-agents", parent)
    )
    if events[-1].type != "run.completed":
        raise RuntimeError("OpenAI Agents Step did not complete")
    result = events[-1].data["result"]
    db.finish_step(input.run_id, "openai", result, events)
    return {"output": result}


def execute(run_id: str, prompt: str, *, command: str | None = None) -> dict:
    db = PgFacts()
    # Inspector has already created the Run in a synchronous POST transaction.
    command = command if command is not None else db.create(run_id, prompt=prompt)
    db.dispatch(command)
    try:
        # Returning the real Hatchet run reference before waiting allows an
        # explicit Provider Binding in Harness PG; not the same as Run terminal.
        ref = workflow.run(LoopInput(run_id=run_id, prompt=prompt),
                           wait_for_result=False)
    except Exception:
        db.unknown(command)  # ACK could have been lost: do not resubmit.
        raise
    db.bind(command, ref.workflow_run_id)
    result = hatchet.runs.get_run_ref(ref.workflow_run_id).result()
    if not isinstance(result, dict):
        raise RuntimeError("Hatchet did not return authoritative workflow result")
    outputs = db.complete(run_id)
    snapshot = db.snapshot(run_id)
    assert snapshot["state"] == "COMPLETED"
    assert snapshot["outbox"] == "CONFIRMED"
    assert all(step["state"] == "COMPLETED" and step["attempts"] == 1
               for step in snapshot["steps"].values())
    assert [e["seq"] for e in snapshot["events"]] == list(
        range(1, len(snapshot["events"]) + 1)
    )
    assert outputs == {
        "pydantic": "pydantic-sdk-real-run",
        "openai": "openai-sdk-real-run",
    }, outputs
    return {
        "outcome": "PASS", "hatchet_engine": "REAL_EMBEDDED_EXTERNAL_DOCKER_PG",
        "platform_facts": "REAL_POSTGRESQL_SEPARATE_DATABASE",
        "domain_run_id": run_id,
        "provider_workflow_id": ref.workflow_run_id,
        "workflow_handoff": "PASS", "two_public_agent_sdks": "PASS",
        "persistent_events": len(snapshot["events"]),
        "domain_run_terminal": snapshot["state"],
        "step_attempts": {name: step["attempts"]
                          for name, step in snapshot["steps"].items()},
        "external_model_calls": 0, "sandbox": "NOT_REQUIRED_MODEL_ONLY",
        "token_sse": "NOT_TESTED", "external_tool_receipt": "NOT_TESTED",
        "two_worker_failover": "NOT_TESTED",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--prompt", default="real sdk and postgres closed loop")
    args = parser.parse_args()
    run_id = args.run_id or f"loop-{uuid4().hex}"
    worker = hatchet.worker("harness-closed-loop-worker", workflows=[workflow])
    threading.Thread(target=worker.start, daemon=True).start()
    time.sleep(5)
    status = 0
    try:
        print(json.dumps(execute(run_id, args.prompt), sort_keys=True), flush=True)
    except Exception:
        status = 1
        traceback.print_exc()
    finally:
        hatchet.stop_embedded()
        # Embedded worker subprocesses may otherwise hold the Python process.
        import sys
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(status)


if __name__ == "__main__":
    main()