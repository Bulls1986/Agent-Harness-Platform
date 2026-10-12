"""OpenCode Native Guest public API behind authoritative Cube PG binding.

This adapter does not allocate Sandboxes, own workflow retries or trust native
OpenCode Session IDs as an authorization grant. Every Guest call selects the
frozen provider Sandbox through CubeWorkspaceGateway._attach(), which checks
PG Owner/Scope/Lease/Fencing and the exact Native provider identity.

Important limitation: the AFTER-call PG check classifies a raced result as
UNKNOWN; it does not cancel an already-running Guest Shell side effect.
Native in-flight revocation requires a separate proven Guest-side barrier.
"""
from __future__ import annotations

import json
import hashlib
import re
import shlex
import time
from uuid import uuid4

from poc.closed_loop.facts import UnsafeDispatch
from poc.sandbox.verify_opencode_guest_http import (
    _guest_http, _safe_server_command,
    native_session_id, resolve_api_prefix,
)


class BoundOpenCodeGuest:
    def __init__(self, workspace, *, password: str):
        if (not isinstance(password, str)
                or len(password) < 32 or not password.isascii()):
            raise ValueError("Trusted OpenCode server secret required")
        self.workspace = workspace
        self.password = password

    @staticmethod
    def _session(session_id: str, prefix: str):
        if not isinstance(session_id, str) or not re.fullmatch(
                r"[A-Za-z0-9_-]{3,128}", session_id):
            raise ValueError("Malformed Native OpenCode Session ID")
        if prefix not in ("", "/api"):
            raise ValueError("Unsupported Native OpenCode API version")

    def start_server(self, execution_id: str, owner: str, epoch: int):
        sb = self.workspace._attach(execution_id, owner, epoch)
        cmd = sb.commands.run(
            _safe_server_command(), timeout=20,
            envs={"OPENCODE_SERVER_PASSWORD": self.password},
        )
        if cmd.exit_code != 0:
            raise UnsafeDispatch("OpenCode server start outcome unknown")
        self.workspace.binding.assert_active(execution_id, owner, epoch)

    def create_session(self, execution_id: str, owner: str, epoch: int):
        native = self.workspace._attach(execution_id, owner, epoch)
        version = native.commands.run("opencode --version", timeout=12)
        if version.exit_code != 0:
            raise UnsafeDispatch("Real Guest OpenCode binary unavailable")
        prefix = resolve_api_prefix(version.stdout.strip())
        native = self.workspace._attach(execution_id, owner, epoch)
        response = _guest_http(
            native, self.password, "POST", prefix + "/session")
        sid = native_session_id(response, prefix)
        self.workspace.binding.assert_active(execution_id, owner, epoch)
        return sid, prefix

    def recover_session(self, execution_id: str, owner: str,
                        epoch: int, session_id: str, prefix: str):
        self._session(session_id, prefix)
        native = self.workspace._attach(execution_id, owner, epoch)
        response = _guest_http(
            native, self.password, "GET",
            prefix + "/session/" + session_id)
        actual_id = native_session_id(response, prefix)
        self.workspace.binding.assert_active(execution_id, owner, epoch)
        if actual_id != session_id:
            raise UnsafeDispatch("Recovered Native Session belongs to another Guest")
        return actual_id

    def _dispatch_shell(self, execution_id: str, owner: str,
                        epoch: int, session_id: str, prefix: str,
                        command: str):
        self._session(session_id, prefix)
        if not isinstance(command, str) or not command.strip():
            raise ValueError("Empty Native Guest Shell command")
        native = self.workspace._attach(execution_id, owner, epoch)
        effect_id = self.workspace.binding.begin_guest_effect(
            execution_id, owner, epoch, "OPENCODE_SHELL",
            "sha256:" + hashlib.sha256(command.encode("utf-8")).hexdigest())
        # This reservation must be durable before contacting the native API.
        # Any transport crash or timeout leaves DISPATCHED, preventing B from
        # replaying the same potentially non-idempotent action.
        response = _guest_http(
            native, self.password, "POST",
            prefix + "/session/" + session_id + "/shell",
            json.dumps({"agent": "build", "command": command}),
        )
        # A PG handoff during the OpenCode command must never turn an
        # uncertain native effect into an acknowledged success.
        self.workspace.binding.assert_active(execution_id, owner, epoch)
        return response, effect_id

    def native_shell(self, execution_id: str, owner: str,
                     epoch: int, session_id: str, prefix: str,
                     command: str):
        # No completion oracle: leave DISPATCHED until an independently
        # verified receipt is reconciled. Never report generic shell output
        # as a confirmed side-effect receipt.
        response, _effect = self._dispatch_shell(
            execution_id, owner, epoch, session_id, prefix, command)
        return response

    def native_shell_verified_file(self, execution_id: str, owner: str,
                                   epoch: int, session_id: str, prefix: str,
                                   command: str, path: str, expected: str):
        # The Native Shell HTTP endpoint may ACK before the Guest process
        # actually finishes. Observing a matching file alone is NOT an
        # authoritative completion receipt: a command could write it and
        # continue running after the new Worker takes over.
        token=uuid4().hex
        receipt_path="/workspace/m5-opencode/.harness-receipts/"+token
        guarded=(
            "mkdir -p /workspace/m5-opencode/.harness-receipts && "
            "sh -c "+shlex.quote(command)+" && "
            "printf "+shlex.quote(token)+" > "+shlex.quote(receipt_path)
        )
        _response, effect_id = self._dispatch_shell(
            execution_id, owner, epoch, session_id, prefix, guarded)
        for _ in range(10):
            try:
                read = self.workspace.read(execution_id, owner, epoch, path)
                completed = self.workspace.read(
                    execution_id, owner, epoch, receipt_path)
            except UnsafeDispatch:
                raise
            except Exception:
                time.sleep(0.5)
                continue
            if read == expected and completed == token:
                # Terminal marker is written only after the foreground shell
                # exits successfully. Detached children and arbitrary coding
                # tools still require their own Guest-side revocation gate.
                self.workspace.binding.confirm_guest_effect(
                    execution_id, owner, epoch, effect_id,
                    "sha256:" + hashlib.sha256(
                        (read+completed).encode("utf-8")).hexdigest())
                return True
            raise UnsafeDispatch("Guest file differs from expected Native Shell effect")
        raise UnsafeDispatch("OpenCode Native Shell terminal receipt not verified")

    def read_native_file(self, execution_id: str, owner: str,
                         epoch: int, prefix: str, filename: str) -> str:
        if (prefix != "/api" or not isinstance(filename, str)
                or not re.fullmatch(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*",
                                    filename)):
            raise ValueError("Native v2 file read must be an in-project basename")
        guest = self.workspace._attach(execution_id, owner, epoch)
        value = _guest_http(guest, self.password, "GET",
                            "/api/fs/read/" + filename)
        self.workspace.binding.assert_active(execution_id, owner, epoch)
        if not isinstance(value, str):
            raise UnsafeDispatch("Invalid OpenCode native Files result")
        return value

    def native_vcs(self, execution_id: str, owner: str,
                   epoch: int, prefix: str) -> dict:
        if prefix != "/api":
            raise ValueError("Native VCS v2 only in this adapter")
        guest = self.workspace._attach(execution_id, owner, epoch)
        result = _guest_http(guest, self.password, "GET", "/api/vcs")
        self.workspace.binding.assert_active(execution_id, owner, epoch)
        if not isinstance(result, dict) or not isinstance(result.get("data"), dict):
            raise UnsafeDispatch("OpenCode Native VCS must return authoritative data")
        return result["data"]
