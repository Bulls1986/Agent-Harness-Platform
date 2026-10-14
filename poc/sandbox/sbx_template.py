"""CubeSandbox native Template SDK boundary; no Harness template definition DSL.

Only SDK-supported operations are exposed and privileged server-side Policy
must authorize each action. Template.build uses OCI image inputs exactly as
Cube's Python SDK accepts; Dockerfile must be built into OCI externally.
"""
from __future__ import annotations

import re
from poc.sandbox.sbx_management import SandboxPermissionDenied

_NATIVE_BUILD = frozenset({
    "image", "name", "writable_layer_size", "exposed_ports", "probe_port",
    "probe_path", "instance_type", "cpu_count", "memory_mb", "envs",
    "allow_internet_access", "network_type", "nodes", "command", "args",
    "dns", "allow_out", "deny_out", "enable_ivshmem",
})
_ALIAS = re.compile(r"[a-z0-9][a-z0-9-]{0,63}\Z")
_TEMPLATE_ID = re.compile(r"tpl-[a-zA-Z0-9_-]{1,128}\Z")


def _identity(scope, principal):
    if not all(isinstance(x, str) and x and x == x.strip()
               for x in (scope, principal)):
        raise ValueError("Trusted scope and principal required")


def _native_ref(reference):
    if not isinstance(reference, str) or not (
            _TEMPLATE_ID.fullmatch(reference) or _ALIAS.fullmatch(reference)
    ):
        raise ValueError("Invalid native Cube template reference")
    return reference


def _dto(row):
    """Safe provider metadata, not raw stored template create_request/secrets."""
    return {
        "template_id": row.template_id,
        "name": getattr(row, "name", ""),
        "status": getattr(row, "status", ""),
        "image_info": getattr(row, "image_info", ""),
        "job_id": getattr(row, "job_id", ""),
    }


class CubeTemplateGateway:
    def __init__(self, *, authorize, sdk=None):
        if not callable(authorize):
            raise ValueError("Explicit server-side Template authorization required")
        if sdk is None:
            from cubesandbox import Template
            sdk = Template
        self.authorize, self.sdk = authorize, sdk

    def _permit(self, scope, principal, action, native):
        _identity(scope, principal)
        if self.authorize(scope, principal, action, native) is not True:
            raise SandboxPermissionDenied("Cube Template operation denied")

    def list(self, *, scope, principal):
        self._permit(scope, principal, "list", {})
        return [_dto(x) for x in self.sdk.list()]

    def get(self, *, scope, principal, template):
        ref = _native_ref(template)
        self._permit(scope, principal, "get", {"template": ref})
        return _dto(self.sdk.get(ref))

    def resolve(self, template):
        """Native alias or ID -> immutable READY template ID (caller already permitted Create)."""
        ref = _native_ref(template)
        try:
            row = self.sdk.get(ref)
        except Exception:
            raise ValueError("Native Cube Template not found or unavailable") from None
        if (getattr(row, "status", None) != "READY"
                or not _TEMPLATE_ID.fullmatch(str(getattr(row, "template_id", "")))):
            raise ValueError("Native Cube Template must be READY with a frozen ID")
        return row.template_id

    def build(self, *, scope, principal, cube):
        self._permit(scope, principal, "build", cube)
        if not isinstance(cube, dict) or set(cube) - _NATIVE_BUILD:
            raise ValueError("Only installed Cube native Template.build fields supported")
        image = cube.get("image")
        if not isinstance(image, str) or not image.strip():
            raise ValueError("Cube native Template.build requires OCI image")
        if "name" in cube and (not isinstance(cube["name"], str) or
                               not _ALIAS.fullmatch(cube["name"])):
            raise ValueError("Invalid Cube Template alias")
        result = self.sdk.build(**cube)
        return {"template_id": result.template_id,
                "job_id": result.job_id,
                "status": result.status}

    def delete(self, *, scope, principal, template):
        ref = _native_ref(template)
        self._permit(scope, principal, "delete", {"template": ref})
        self.sdk.delete(ref)
        return None

    def set_alias(self, *, scope, principal, template, alias):
        ref = _native_ref(template)
        if not isinstance(alias, str) or not _ALIAS.fullmatch(alias):
            raise ValueError("Invalid native Cube alias")
        self._permit(scope, principal, "alias", {"template": ref, "alias": alias})
        return _dto(self.sdk.set_alias(ref, alias))