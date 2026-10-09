"""G3 bounded live-model protocol adapter: MAF -> PostgreSQL facts -> SSE.

Only committed model output is published. No fabricated tokens, tool calls,
file access, history persistence, or automatic retry.
"""
from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

import psycopg
from psycopg.rows import dict_row

from task_ledger import TaskFactConflict, TaskLedger, _id


class LiveModelLedger(TaskLedger):
    def create(self, *, model: str, initiator: str = "poc-live-initiator") -> tuple[str, str, str, str]:
        conversation_id, turn_id, run_id = _id("conversation"), _id("turn"), _id("run")
        plan_id, step_id, attempt_id, execution_id = (
            _id("plan"), _id("step"), _id("attempt"), _id("execution")
        )
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO poc_conversations(conversation_id) VALUES (%s)", (conversation_id,))
                cur.execute("INSERT INTO poc_turns(turn_id,conversation_id) VALUES (%s,%s)",
                            (turn_id, conversation_id))
                cur.execute("""INSERT INTO poc_runs(run_id,turn_id,initiator_principal_id,
                    runtime_type,recipe_version,state)
                    VALUES (%s,%s,%s,'maf','poc-live-model-v1','RUNNING')""",
                            (run_id, turn_id, initiator))
                cur.execute("""INSERT INTO poc_plans(plan_id,run_id,version,reason)
                    VALUES (%s,%s,1,'model response')""", (plan_id, run_id))
                cur.execute("""INSERT INTO poc_steps(step_id,plan_id,ordinal,intent)
                    VALUES (%s,%s,1,'Stream a model-only response')""", (step_id, plan_id))
                cur.execute("""INSERT INTO poc_attempts(attempt_id,step_id,ordinal,state)
                    VALUES (%s,%s,1,'RUNNING')""", (attempt_id, step_id))
                cur.execute("""INSERT INTO poc_executions(execution_id,attempt_id,side_effect_class,state)
                    VALUES (%s,%s,'PURE','RUNNING')""", (execution_id, attempt_id))
                cur.execute("""INSERT INTO poc_runtime_bindings(run_id,runtime_type)
                    VALUES (%s,'maf')""", (run_id,))
                cur.execute("""INSERT INTO poc_events(event_id,run_id,seq,event_type,payload)
                    VALUES (%s,%s,1,'run.started',%s::jsonb)""",
                            (_id("event"), run_id, json.dumps({
                                "step_id": step_id, "attempt_id": attempt_id, "model": model
                            })))
        return run_id, step_id, attempt_id, execution_id

    def append_delta(self, run_id: str, step_id: str, attempt_id: str, delta: str) -> dict:
        if not delta:
            raise ValueError("Empty model delta must not produce an event")
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT state FROM poc_runs WHERE run_id=%s FOR UPDATE", (run_id,))
                row = cur.fetchone()
                if not row or row["state"] != "RUNNING":
                    raise TaskFactConflict("Live Run is not active")
                seq = cur.execute("SELECT COALESCE(MAX(seq),0)+1 AS seq FROM poc_events WHERE run_id=%s",
                                  (run_id,)).fetchone()["seq"]
                payload = {"step_id": step_id, "attempt_id": attempt_id, "delta": delta}
                cur.execute("""INSERT INTO poc_events(event_id,run_id,seq,event_type,payload)
                    VALUES (%s,%s,%s,'response.output_text.delta',%s::jsonb)""",
                            (_id("event"), run_id, seq, json.dumps(payload)))
                return {"seq": seq, "event_type": "response.output_text.delta", "payload": payload}

    def terminate(self, run_id: str, attempt_id: str, execution_id: str,
                  *, completed: bool, failure_type: str | None = None) -> dict:
        state = "COMPLETED" if completed else "FAILED"
        attempt_state = "SUCCEEDED" if completed else "FAILED"
        if not completed and not failure_type:
            raise ValueError("Failed stream requires failure classification")
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT state FROM poc_runs WHERE run_id=%s FOR UPDATE", (run_id,))
                row = cur.fetchone()
                if not row or row["state"] != "RUNNING":
                    raise TaskFactConflict("Cannot terminate inactive/terminal Run")
                cur.execute("""UPDATE poc_attempts SET state=%s,failure_type=%s
                    WHERE attempt_id=%s AND state='RUNNING'""",
                            (attempt_state, failure_type, attempt_id))
                if cur.rowcount != 1:
                    raise TaskFactConflict("Attempt not active")
                cur.execute("""UPDATE poc_executions SET state=%s,failure_type=%s
                    WHERE execution_id=%s AND attempt_id=%s AND state='RUNNING'""",
                            (attempt_state, failure_type, execution_id, attempt_id))
                if cur.rowcount != 1:
                    raise TaskFactConflict("Execution not active")
                cur.execute("UPDATE poc_runs SET state=%s,terminal_at=now() WHERE run_id=%s",
                            (state, run_id))
                seq = cur.execute("SELECT COALESCE(MAX(seq),0)+1 AS seq FROM poc_events WHERE run_id=%s",
                                  (run_id,)).fetchone()["seq"]
                payload = {"state": state, "attempt_id": attempt_id}
                if failure_type:
                    payload["failure_type"] = failure_type
                cur.execute("""INSERT INTO poc_events(event_id,run_id,seq,event_type,payload)
                    VALUES (%s,%s,%s,'run.terminal',%s::jsonb)""",
                            (_id("event"), run_id, seq, json.dumps(payload)))
                return {"seq": seq, "event_type": "run.terminal", "payload": payload}


async def provider_deltas(*, prompt: str, model: str, base_url: str,
                          api_key: str) -> AsyncIterator[str]:
    """Only real nonempty chunks from official MAF public streaming APIs."""
    from agent_framework import create_harness_agent
    from agent_framework.openai import OpenAIChatClient

    client = OpenAIChatClient(model=model, base_url=base_url, api_key=api_key)
    agent = create_harness_agent(
        client=client, name="maf-platform-live-protocol-poc",
        # Harness Todo/Mode tools are enabled by default. A text-only proof
        # must disable them explicitly, not merely disable auto approval.
        tools=[], disable_todo=True, disable_mode=True,
        disable_file_memory=True, disable_web_search=True,
        disable_tool_auto_approval=True, disable_compaction=True,
        default_options={"store": False, "max_output_tokens": 128},
    )
    session = agent.create_session()
    async for chunk in agent.run(prompt, session=session, stream=True):
        delta = getattr(chunk, "text", None)
        if delta:
            yield delta


async def persisted_model_events(ledger: LiveModelLedger, *,
                                 run_id: str, step_id: str, attempt_id: str,
                                 execution_id: str, prompt: str, model: str,
                                 base_url: str, api_key: str):
    """Persist-before-publish; provider failures cannot create fake assistant text."""
    count = 0
    try:
        async with asyncio.timeout(120):
            async for delta in provider_deltas(
                prompt=prompt, model=model, base_url=base_url, api_key=api_key
            ):
                row = await asyncio.to_thread(
                    ledger.append_delta, run_id, step_id, attempt_id, delta
                )
                count += 1
                yield row
    except (asyncio.CancelledError, GeneratorExit):
        # Task cancellation and async-generator aclose() are distinct client
        # disconnect paths. Neither may leave an active Run falsely RUNNING.
        await asyncio.to_thread(ledger.terminate, run_id, attempt_id, execution_id,
                                completed=False, failure_type="STREAM_DISCONNECTED")
        raise
    except Exception:
        row = await asyncio.to_thread(
            ledger.terminate, run_id, attempt_id, execution_id,
            completed=False, failure_type="MODEL_STREAM_INTERRUPTED"
        )
        yield row
        return
    row = await asyncio.to_thread(
        ledger.terminate, run_id, attempt_id, execution_id,
        completed=count > 0, failure_type=None if count else "EMPTY_MODEL_STREAM"
    )
    yield row
