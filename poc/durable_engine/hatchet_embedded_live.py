"""Real Hatchet Embedded DAG with two public Agent SDKs.

Gates: real engine, DAG handoff, Pydantic AI, OpenAI Agents SDK.
NOT tested: cross-worker failover, HITL, Cube, token SSE, Tool Receipt.
No mock Hatchet engine is permitted in this test.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import tempfile
import threading
import time

from hatchet_sdk import Context, Hatchet
from pydantic import BaseModel
from poc.runtime_spi.contract import AgentRuntimeDispatcher, ExecutionContext, RunRequest

# Hatchet SDK recognizes subprocess imports and attaches them to parent's engine.
hatchet = Hatchet.from_embedded()


class PipelineInput(BaseModel):
    run_id: str
    prompt: str = "test agent handoff"


pipeline = hatchet.workflow(
    name="harness-durable-embedded-smoke",
    input_validator=PipelineInput,
)


def context(run_id: str, runtime: str) -> ExecutionContext:
    return ExecutionContext(
        run_id=run_id, turn_id=run_id + ":turn",
        session_id=run_id + ":session", isolation_scope="model-only-poc",
        execution_id=run_id + ":" + runtime,
        owner_id="hatchet-poc-worker", fencing_token=1,
    )


def evidence(stage: str, value: str) -> None:
    folder = Path(os.environ["HATCHET_POC_EVIDENCE_DIR"])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / (stage + ".json")).write_text(
        json.dumps({"stage": stage, "result": value}), encoding="utf-8"
    )


@pipeline.task()
async def pydantic_stage(input: PipelineInput, ctx: Context) -> dict[str, str]:
    from pydantic_ai import Agent
    from pydantic_ai.messages import ModelResponse, TextPart
    from pydantic_ai.models.function import FunctionModel
    from poc.runtime_spi.adapters import PydanticRuntimeAdapter

    def model(messages, info):
        return ModelResponse(parts=[TextPart("pydantic-sdk-real-run")])

    adapter = PydanticRuntimeAdapter(Agent(FunctionModel(model)))
    events = await AgentRuntimeDispatcher(adapter).execute(
        RunRequest(context(input.run_id, "pydantic"), "pydantic", input.prompt)
    )
    assert events[-1].type == "run.completed"
    output = events[-1].data["result"]
    evidence("pydantic", output)
    return {"output": output}


@pipeline.task(parents=[pydantic_stage])
async def openai_stage(input: PipelineInput, ctx: Context) -> dict[str, str]:
    from agents import Agent
    from agents.models.interface import Model, ModelResponse
    from agents.usage import Usage
    from openai.types.responses import ResponseOutputMessage, ResponseOutputText
    from poc.runtime_spi.adapters import OpenAIAgentsRuntimeAdapter

    first = ctx.task_output(pydantic_stage)
    assert first["output"] == "pydantic-sdk-real-run", first

    class LocalModel(Model):
        async def get_response(self, *args, **kwargs):
            msg = ResponseOutputMessage(
                id="hatchet-local", role="assistant", type="message",
                status="completed", content=[
                    ResponseOutputText(
                        annotations=[], text="openai-sdk-real-run",
                        type="output_text"
                    )
                ],
            )
            return ModelResponse(
                output=[msg], usage=Usage(requests=1),
                response_id="hatchet-local-response",
            )

        async def stream_response(self, *args, **kwargs):
            if False:
                yield None
            raise NotImplementedError("Token SSE outside this gate")

    adapter = OpenAIAgentsRuntimeAdapter(
        Agent(name="hatchet-local", model=LocalModel())
    )
    events = await AgentRuntimeDispatcher(adapter).execute(
        RunRequest(
            context(input.run_id, "openai-agents"),
            "openai-agents", first["output"]
        )
    )
    assert events[-1].type == "run.completed"
    output = events[-1].data["result"]
    evidence("openai", output)
    return {"input": first["output"], "output": output}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="hatchet-smoke-001")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="hatchet-poc-") as tmp:
        os.environ["HATCHET_POC_EVIDENCE_DIR"] = tmp
        worker = hatchet.worker(
            "harness-durable-embedded-worker", workflows=[pipeline]
        )
        threading.Thread(target=worker.start, daemon=True).start()
        time.sleep(4)  # Upstream Embedded example uses start + bounded sleep.
        try:
            result = pipeline.run(PipelineInput(run_id=args.run_id))
            p = json.loads((Path(tmp) / "pydantic.json").read_text())
            o = json.loads((Path(tmp) / "openai.json").read_text())
            assert isinstance(result, dict)
            assert p["result"] == "pydantic-sdk-real-run", p
            assert o["result"] == "openai-sdk-real-run", o
            print(json.dumps({
                "outcome": "PASS",
                "hatchet_engine": "REAL_EMBEDDED",
                "pydantic_public_sdk": "PASS",
                "openai_public_sdk": "PASS",
                "dag_parent_handoff": "PASS",
                "remote_model_calls": 0,
                "worker_b_failover": "NOT_TESTED",
                "approval": "NOT_TESTED",
                "cube": "NOT_TESTED",
                "token_sse": "NOT_TESTED",
                "external_receipt": "NOT_TESTED",
            }, sort_keys=True), flush=True)
        finally:
            hatchet.stop_embedded()
    # Follows Hatchet's public Embedded Python example: worker subprocesses
    # may otherwise keep interpreter alive after stopping the engine.
    os._exit(0)


if __name__ == "__main__":
    main()
