"""Local-only Inspector HTTP facade over PostgreSQL Harness facts.

Zero fake successes. Production identity, auth, SSE, and Cube are NOT supplied.
Passing a submit callback is an explicit server obligation: the callback must
enqueue a REAL Hatchet run, not a parallel task scheduler.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from .facts import PgFacts


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
) -> FastAPI:
    app = FastAPI(title="Harness Run Inspector (Local POC)", version="0.1.0")
    index = Path(__file__).with_name("inspector.html")

    def facts() -> PgFacts:
        try:
            return facts_factory()
        except Exception:
            raise HTTPException(503, "Harness PostgreSQL unavailable") from None

    @app.get("/", include_in_schema=False)
    def home():
        return FileResponse(index, media_type="text/html")

    @app.post("/api/runs", status_code=202)
    def create_run(body: RunCreate):
        if submit is None:
            raise HTTPException(503, "Real Hatchet runner is unavailable")
        db = facts()
        run_id = "run-" + uuid4().hex
        try:
            key = db.create(run_id)
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

    @app.get("/api/runs/{run_id}/events")
    def events(run_id: str, after: int = Query(0, ge=0)):
        snapshot = get_run(run_id)
        return {"run_id": run_id, "events": [
            item for item in snapshot["events"] if item["seq"] > after
        ], "cursor": snapshot["events"][-1]["seq"] if snapshot["events"] else 0}

    return app