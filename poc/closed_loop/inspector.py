"""Local-only Inspector HTTP facade over PostgreSQL Harness facts.

Zero fake successes. Production identity, auth, SSE, and Cube are NOT supplied.
Passing a submit callback is an explicit server obligation: the callback must
enqueue a REAL Hatchet run, not a parallel task scheduler.
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Callable
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from .facts import PgFacts
from .trusted_scenario_runner import TrustedScenarioRunner


class RunCreate(BaseModel):
    prompt: str = Field(min_length=1, max_length=4096)

    @field_validator("prompt")
    @classmethod
    def check_prompt(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Prompt cannot be blank")
        return value.strip()


def create_app(
    *,
    facts_factory: Callable[[], PgFacts] = PgFacts,
    submit: Callable[[str, str, str], object] | None = None,
    trusted_runner: TrustedScenarioRunner | None = None,
) -> FastAPI:
    app = FastAPI(title="Harness Run Inspector (Local POC)", version="0.1.0")
    index = Path(__file__).with_name("inspector.html")

    def facts() -> PgFacts:
        try:
            return facts_factory()
        except Exception:
            raise HTTPException(503, "Harness PostgreSQL unavailable") from None

    @app.get("/api/verification/scenarios")
    def capability_scenarios():
        from .capability_inspector import catalog
        result = catalog()
        # Never mutate the module-global static catalog for other app instances.
        result["scenarios"] = [dict(scene) for scene in result["scenarios"]]
        if trusted_runner is not None:
            for scene in result["scenarios"]:
                if scene["id"] == "worker-takeover":
                    scene["availability"] = "EXECUTABLE_OPERATOR_AUTH"
                    scene["limitations"] = (
                        scene["limitations"] +
                        " 仅显式授权的 Linux 开发机可触发；需要现场确认运行权限，"
                        "完整 OpenCode/生产安全与容量门禁仍未证明。"
                    )
        return result

    def require_operator(request: Request) -> TrustedScenarioRunner:
        if trusted_runner is None:
            raise HTTPException(503, "Privileged scenario runner disabled")
        # The HTTP service is meant to be bound only to 127.0.0.1. A
        # browser-supplied Host header alone cannot establish local authority.
        if request.client and request.client.host not in (
                "127.0.0.1", "::1", "testclient"):
            raise HTTPException(403, "Local operator only")
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") not in (
                str(request.base_url).rstrip("/"),
                "http://127.0.0.1:8765", "http://localhost:8765"):
            raise HTTPException(403, "Cross-origin execution forbidden")
        if not trusted_runner.authorized(
                request.headers.get("X-Inspector-Scenario-Token")):
            raise HTTPException(403, "Operator authorization required")
        return trusted_runner

    @app.post("/api/verification/scenarios/worker-takeover/runs",
              status_code=202)
    def start_native_scenario(request: Request):
        runner = require_operator(request)
        try:
            proof_id = runner.start()
        except RuntimeError:
            raise HTTPException(409, "A native execution is active or requires reconciliation") from None
        except Exception:
            raise HTTPException(503, "Unable to persist trusted execution") from None
        return {"execution_id": proof_id, "status": "RUNNING",
                "verified": False}

    @app.get("/api/verification/executions/{execution_id}")
    def native_execution_evidence(execution_id: str, request: Request):
        runner = require_operator(request)
        try:
            return runner.get(execution_id)
        except KeyError:
            raise HTTPException(404, "Unknown authorized execution") from None

    @app.get("/api/verification/evidence/{run_id}")
    def capability_evidence(run_id: str):
        from .capability_inspector import evidence
        # POC Run identifiers are bounded and path-safe; never infer a
        # capability's success from an arbitrary URL, prompt or fake event.
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", run_id):
            raise HTTPException(422, "Invalid Run ID")
        try:
            return evidence(facts(), run_id)
        except KeyError:
            raise HTTPException(404, "Unknown Run") from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Unable to read authoritative capability evidence") from None

    @app.get('/api/config')
    def get_model_config():
        from .real_model import ModelConfiguration
        try:
            cfg = ModelConfiguration.from_env()
        except ValueError:
            raise HTTPException(503, 'Real model configuration missing/invalid') from None
        # Only non-sensitive metadata: never return endpoint/key/authorization.
        return {'mode': cfg.mode, 'model_id': cfg.model_id,
                'real_token_sse': ('MODEL_TEXT_AVAILABLE_LIMITED_POC'
                                   if cfg.mode=='live' else 'NO_UPSTREAM_LOCAL')}

    @app.get("/", include_in_schema=False)
    def home():
        return FileResponse(index, media_type="text/html")

    @app.post("/api/runs", status_code=202)
    def create_run(body: RunCreate):
        if submit is None:
            raise HTTPException(503, "Real Hatchet runner is unavailable")
        from .real_model import ModelConfiguration
        try:
            cfg = ModelConfiguration.from_env()
        except ValueError:
            raise HTTPException(503, 'Real model configuration missing/invalid') from None
        db = facts()
        run_id = "run-" + uuid4().hex
        try:
            key = db.create(run_id, prompt=body.prompt,
                            model_mode=cfg.mode, model_id=cfg.model_id)
        except Exception:
            raise HTTPException(503, "Unable to create persisted Run") from None
        try:
            submit(run_id, body.prompt, key)
        except Exception:
            try:
                db.report_execution_error(run_id, "SUBMISSION_FAILED")
            except Exception:
                pass
            # A durable Run exists; the client must never assume it completed.
            raise HTTPException(503, detail={
                "message": "Hatchet dispatch unavailable; persisted Run needs reconciliation",
                "run_id": run_id,
            }) from None
        return {"run_id": run_id, "state": "CREATED"}

    @app.get("/api/runs")
    def list_runs(limit: int = Query(20, ge=1, le=100)):
        try:
            return {"runs": facts().list_runs(limit)}
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Unable to query Run history") from None

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str):
        try:
            return facts().snapshot(run_id)
        except KeyError:
            raise HTTPException(404, "Unknown Run") from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Unable to read Run facts") from None

    @app.post('/api/runs/{run_id}/cancel',status_code=202)
    def cancel_run(run_id: str):
        from .facts import UnsafeDispatch
        try:
            state=facts().request_cancel(run_id)
        except KeyError: raise HTTPException(404,'Unknown Run') from None
        except UnsafeDispatch as exc: raise HTTPException(409,str(exc)) from None
        return {'run_id':run_id,'state':state,'acknowledged':False}

    @app.get('/api/runs/{run_id}/stream')
    async def sse_stream(run_id: str, request: Request,
                         after: int = Query(0,ge=0)):
        import asyncio
        import json
        import time
        from fastapi.responses import StreamingResponse
        db=facts()
        try: db.run_state(run_id)
        except KeyError: raise HTTPException(404,'Unknown Run') from None
        cursor=request.headers.get('last-event-id')
        if cursor is not None:
            prefix=run_id+':'
            num=cursor[len(prefix):] if cursor.startswith(prefix) else ''
            if not num.isdigit():
                raise HTTPException(422,'Invalid or cross-Run Last-Event-ID')
            after=int(num)
        async def generate():
            pos=after
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                if await request.is_disconnected(): break
                batch=await asyncio.to_thread(db.events_since,run_id,pos)
                for evt in batch:
                    pos=evt['seq']
                    body=json.dumps({'run_id':run_id,'seq':pos,'type':evt['type'],
                                     'data':evt['data']},ensure_ascii=False)
                    yield ('id: '+run_id+':'+str(pos)+'\n' +
                           'event: '+evt['type']+'\n'+'data: '+body+'\n\n')
                state=await asyncio.to_thread(db.run_state,run_id)
                finished=(state in ('COMPLETED','CANCELLED') or any(
                    x['type']=='workflow.observation_error' for x in batch))
                # Drain every persisted event page before closing terminal SSE.
                if finished and len(batch)<250: break
                if not batch: yield ': keepalive\n\n'
                await asyncio.sleep(0.35)
        return StreamingResponse(generate(),media_type='text/event-stream',
                                 headers={'Cache-Control':'no-store',
                                          'X-Accel-Buffering':'no'})
    @app.get("/api/runs/{run_id}/events")
    def events(run_id: str, after: int = Query(0, ge=0)):
        snapshot = get_run(run_id)
        return {"run_id": run_id, "events": [
            item for item in snapshot["events"] if item["seq"] > after
        ], "cursor": snapshot["events"][-1]["seq"] if snapshot["events"] else 0}

    return app
