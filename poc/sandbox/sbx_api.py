"""DEV-SBX M1 experimental authorized HTTP Create/Operation interface.

Keep separate from M7 and Inspector default demo; requires a real trusted
Gateway resolve_context and SandboxCreateService with an explicit Policy.
"""
from __future__ import annotations

from typing import Any, Callable
from fastapi import FastAPI, HTTPException, Header, Request
from pydantic import BaseModel, Field

from poc.sandbox.sbx_management import (
    SandboxCreateService, SandboxConflict, SandboxPermissionDenied,
    SandboxUnknown,
)


class SandboxCreateRequest(BaseModel):
    cube: dict[str, Any]
    onCreate: dict[str, list[dict[str, Any]]] = Field(
        default_factory=lambda: {"commands": []})


def _public(row):
    return {
        "operationId": row["operation_id"],
        "sandboxRef": row["sandbox_id"],
        "nativeTemplateId": row["template_id"],
        "state": row["state"],
        "exitCode": row["exit_code"],
    }


def create_sbx_m1_app(*, resolve_context: Callable, service: SandboxCreateService):
    if not callable(resolve_context) or not isinstance(service, SandboxCreateService):
        raise ValueError("Trusted context resolver and Sandbox Create service required")
    app = FastAPI(title="DEV-SBX M1 Cube-native Create (limited development)",
                  version="0.1.0")

    def identity(request: Request):
        context = resolve_context(request)
        if context is None:
            raise HTTPException(401, "Authentication required")
        scope = getattr(context, "project_scope", None)
        principal = getattr(context, "principal_id", None)
        if not scope or not principal:
            raise HTTPException(401, "Trusted scoped identity required")
        return scope, principal

    @app.post("/api/v1/sandboxes", status_code=202)
    def create(body: SandboxCreateRequest, request: Request,
               idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
        scope, principal = identity(request)
        if not idempotency_key:
            raise HTTPException(400, "Idempotency-Key required")
        try:
            commands = body.onCreate.get("commands")
            if set(body.onCreate) != {"commands"}:
                raise ValueError("Only onCreate.commands is supported")
            return _public(service.create(
                scope=scope, principal=principal, idempotency_key=idempotency_key,
                cube=body.cube, on_create=commands))
        except SandboxPermissionDenied:
            raise HTTPException(403, "Sandbox Create denied") from None
        except SandboxConflict:
            raise HTTPException(409, "Idempotency/Operation conflict") from None
        except SandboxUnknown:
            raise HTTPException(503, "Sandbox operation UNKNOWN; retry with same Idempotency-Key to retrieve status") from None
        except ValueError:
            raise HTTPException(422, "Unsupported or invalid Cube native parameter / initialization") from None

    @app.get("/api/v1/sandbox-operations/{operation_id}")
    def operation(operation_id: str, request: Request):
        scope, principal = identity(request)
        try:
            return _public(service.get(
                scope=scope, principal=principal, operation_id=operation_id))
        except KeyError:
            raise HTTPException(404, "Not found") from None

    return app