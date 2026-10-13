"""Fail-closed, read-only Run access boundary for DEV-M7.

Authentication remains owned by an external trusted gateway. Its adapter
MUST resolve identity from verified server-side authentication state, never
from client-supplied principal/project headers. The injected Reader supplies
persisted Harness Run facts; the Policy adapter makes current decisions.
This is a small contract slice, not the complete production gateway, and
does not expose Inspector's unauthenticated POC endpoints.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from fastapi import FastAPI, HTTPException, Query, Request


@dataclass(frozen=True)
class SecurityContext:
    principal_id: str
    principal_type: str
    project_scope: str | None = None

    def __post_init__(self):
        if not self.principal_id or not self.principal_id.strip():
            raise ValueError("An authenticated principal is required")
        if self.principal_type not in ("USER", "SERVICE"):
            raise ValueError("Unsupported principal type")


@dataclass(frozen=True)
class RunBinding:
    run_id: str
    project_scope: str
    initiator_principal_id: str

    def __post_init__(self):
        if not all(v and v.strip() for v in (
            self.run_id, self.project_scope, self.initiator_principal_id
        )):
            raise ValueError("Incomplete immutable Run ownership facts")


class RunReader(Protocol):
    def binding(self, run_id: str) -> RunBinding: ...
    def snapshot(self, run_id: str) -> dict: ...
    def events_since(self, run_id: str, after: int, limit: int) -> list[dict]: ...


def create_read_app(
    *,
    resolve_context: Callable[[Request], SecurityContext],
    reader: RunReader,
    authorize: Callable[[SecurityContext, RunBinding, str], bool],
) -> FastAPI:
    """Mount authenticated Run reads; intentionally no identity/header fallback.

    A production deployment must provide a verified IdP/gateway adapter, a
    real PG-backed Run ownership reader, and a current Policy Decision adapter.
    Missing any dependency is a startup/configuration error, not anonymous mode.
    """
    if not callable(resolve_context) or reader is None or not callable(authorize):
        raise ValueError("Trusted identity, persisted Reader and Policy are required")

    app = FastAPI(title="Harness Authorized Run Reads", version="0.1.0")

    def allowed(request: Request, run_id: str, action: str) -> None:
        try:
            context = resolve_context(request)
        except Exception:
            raise HTTPException(401, "Authentication required") from None
        if not isinstance(context, SecurityContext):
            raise HTTPException(401, "Authentication required")
        # A resource-scoped API cannot silently downgrade to an unscoped read.
        if not context.project_scope or not context.project_scope.strip():
            raise HTTPException(404, "Run not found")

        try:
            binding = reader.binding(run_id)
        except KeyError:
            raise HTTPException(404, "Run not found") from None
        except Exception:
            raise HTTPException(503, "Run access unavailable") from None
        if (not isinstance(binding, RunBinding)
                or binding.run_id != run_id
                or context.project_scope != binding.project_scope):
            raise HTTPException(404, "Run not found")
        # A project-wide ALLOW cannot grant access to another USER's Run.
        if (context.principal_type == "USER"
                and context.principal_id != binding.initiator_principal_id):
            raise HTTPException(404, "Run not found")
        try:
            decision = authorize(context, binding, action)
        except Exception:
            raise HTTPException(503, "Run access unavailable") from None
        # Only an explicit ALLOW from the current Policy Decision grants access.
        if decision is not True:
            raise HTTPException(404, "Run not found")
        return context, binding

    @app.get("/api/runs/{run_id}")
    def read_run(run_id: str, request: Request):
        allowed(request, run_id, "run.read")
        try:
            return reader.snapshot(run_id)
        except KeyError:
            raise HTTPException(404, "Run not found") from None
        except Exception:
            raise HTTPException(503, "Run facts unavailable") from None

    @app.get("/api/runs/{run_id}/events")
    def read_events(run_id: str, request: Request,
                    after: int = Query(0, ge=0),
                    limit: int = Query(250, ge=1, le=250)):
        allowed(request, run_id, "run.events.read")
        try:
            events = reader.events_since(run_id, after, limit)
        except KeyError:
            raise HTTPException(404, "Run not found") from None
        except Exception:
            raise HTTPException(503, "Run events unavailable") from None
        return {"run_id": run_id, "events": events,
                "cursor": events[-1]["seq"] if events else after}

    # Reuse the exact same trusted identity/Policy gate for versioned M7
    # run APIs and SSE; do not add a second or header-auth fallback path.
    app.state.require_run_access = allowed

    return app