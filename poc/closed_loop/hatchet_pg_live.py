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
from poc.closed_loop.real_model import (
    ModelConfiguration, make_pydantic_agent, make_openai_agent,
    parse_requirements, parse_review, render_business_report,
)
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


_runtime_config = ModelConfiguration.from_env()
# Different certified Worker capabilities MUST NOT share the same Hatchet
# workflow name: otherwise a pre-existing local-only Worker can claim a live
# Run and silently return fixed fake output.
_workflow_name = ('harness-pg-real-responses-v1' if _runtime_config.mode == 'live'
                  else 'harness-pg-minimal-run-v1')
workflow = hatchet.workflow(
    name=_workflow_name,
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
    cfg = ModelConfiguration.from_env()
    db.assert_model_binding(input.run_id, cfg.mode, cfg.model_id)
    cached = db.start_step(input.run_id, "pydantic", input.prompt)
    if cached is not None:
        return {"output": cached}

    def model(messages, info):
        return ModelResponse(parts=[TextPart("pydantic-sdk-real-run")])

    agent = make_pydantic_agent(cfg) if cfg.mode == 'live' else Agent(FunctionModel(model))
    adapter = PydanticRuntimeAdapter(agent)
    events = await AgentRuntimeDispatcher(adapter).execute(
        RunRequest(runtime_context(input.run_id, "pydantic"), "pydantic", input.prompt)
    )
    if events[-1].type != "run.completed":
        raise RuntimeError("Pydantic SDK Step did not complete")
    result = events[-1].data["result"]
    if cfg.mode == 'live':
        # Verification Gate: never release Step B on malformed model content.
        result = parse_requirements(result).model_dump_json()
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
    cfg = ModelConfiguration.from_env()
    db.assert_model_binding(input.run_id, cfg.mode, cfg.model_id)
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

    agent = (make_openai_agent(cfg) if cfg.mode == 'live'
             else Agent(name="closed-loop", model=LocalModel()))
    adapter = OpenAIAgentsRuntimeAdapter(agent)
    events = await AgentRuntimeDispatcher(adapter).execute(
        RunRequest(runtime_context(input.run_id, "openai-agents"),
                   "openai-agents", parent)
    )
    if events[-1].type != "run.completed":
        raise RuntimeError("OpenAI Agents Step did not complete")
    result = events[-1].data["result"]
    if cfg.mode == 'live':
        draft = parse_requirements(parent)
        review = parse_review(result)
        result = render_business_report(draft, review)
    db.finish_step(input.run_id, "openai", result, events)
    return {"output": result}


def execute(run_id: str, prompt: str, *, command: str | None = None) -> dict:
    db = PgFacts()
    # Inspector has already created the Run in a synchronous POST transaction.
    cfg = ModelConfiguration.from_env()
    command = (command if command is not None else db.create(
        run_id, prompt=prompt, model_mode=cfg.mode, model_id=cfg.model_id))
    db.assert_model_binding(run_id, cfg.mode, cfg.model_id)
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
    # Verify committed actual Step data BEFORE writing the parent business
    # terminal. Provider workflow success alone is never business success.
    prior = db.snapshot(run_id)
    observed = {name: step['output'] for name, step in prior['steps'].items()}
    if cfg.mode == 'live':
        parse_requirements(observed['pydantic'])
        if not isinstance(observed['openai'], str) or not observed['openai'].startswith('【需求分析】'):
            raise ValueError('Missing verified live business report')
    outputs = db.complete(run_id, verified_outputs=observed if cfg.mode == 'live' else None)
    snapshot = db.snapshot(run_id)
    assert snapshot["state"] == "COMPLETED"
    assert snapshot["outbox"] == "CONFIRMED"
    assert all(step["state"] == "COMPLETED" and step["attempts"] == 1
               for step in snapshot["steps"].values())
    assert [e["seq"] for e in snapshot["events"]] == list(
        range(1, len(snapshot["events"]) + 1)
    )
    if cfg.mode == 'live':
        assert parse_requirements(outputs['pydantic'])
        assert '【需求分析】' in outputs['openai']
        assert snapshot['result']['model_id'] == cfg.model_id
    else:
        assert outputs == {
            'pydantic': 'pydantic-sdk-real-run',
            'openai': 'openai-sdk-real-run',
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
        "model_mode": cfg.mode, "model_id": cfg.model_id,
        "external_model_calls": 2 if cfg.mode == 'live' else 0,
        "sandbox": "NOT_REQUIRED_MODEL_ONLY",
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