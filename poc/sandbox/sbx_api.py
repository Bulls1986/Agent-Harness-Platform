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


def create_sbx_m1_app(*, resolve_context: Callable, service: SandboxCreateService, template_gateway=None):
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


    @app.post("/api/v1/sandbox-operations/{operation_id}/reconcile", status_code=202)
    def reconcile(operation_id: str, request: Request):
        scope, principal = identity(request)
        try:
            return _public(service.reconcile(
                scope=scope, principal=principal, operation_id=operation_id))
        except KeyError:
            raise HTTPException(404, "Not found") from None
        except SandboxUnknown:
            raise HTTPException(409, "Cube native evidence not verified; stays UNKNOWN") from None

    if template_gateway is not None:
        from poc.sandbox.sbx_template import CubeTemplateGateway
        if not isinstance(template_gateway, CubeTemplateGateway):
            raise ValueError("Native Cube Template Gateway required")

        def native_action(action, request, **kwargs):
            scope, principal = identity(request)
            try:
                return getattr(template_gateway, action)(
                    scope=scope, principal=principal, **kwargs)
            except SandboxPermissionDenied:
                raise HTTPException(403, "Template administration denied") from None
            except ValueError:
                raise HTTPException(422, "Unsupported native Cube Template request") from None
            except KeyError:
                raise HTTPException(404, "Native Cube Template not found") from None
            except Exception:
                # Native mutating ACK may be ambiguous. Do not auto-resubmit.
                raise HTTPException(503, "Cube native operation unavailable or outcome unknown") from None

        @app.get("/api/v1/cube/templates")
        def list_templates(request: Request):
            return native_action("list", request)

        @app.get("/api/v1/cube/templates/{template}")
        def get_template(template: str, request: Request):
            return native_action("get", request, template=template)

        @app.post("/api/v1/cube/templates/build", status_code=202)
        def build_template(body: dict[str, Any], request: Request):
            return native_action("build", request, cube=body)

        @app.put("/api/v1/cube/templates/{template}/alias")
        def template_alias(template: str, body: dict[str, str], request: Request):
            if set(body) != {"alias"}:
                raise HTTPException(422, "Only Cube native alias update supported")
            return native_action("set_alias", request,
                                 template=template, alias=body["alias"])

        @app.delete("/api/v1/cube/templates/{template}", status_code=204)
        def delete_template(template: str, request: Request):
            native_action("delete", request, template=template)
            return None

    return app