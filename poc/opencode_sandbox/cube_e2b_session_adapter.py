"""POC: platform-approved OpenCode Session -> existing Cube/E2B Sandbox ID.

This adapter DOES NOT patch OpenCode's native Shell/FS/PTY APIs. It can only
serve execution requests explicitly routed through it (e.g. a registered V2
Tool executor receiving context.sessionID).

Production must use trusted Run/Scope/Generation from control-plane admission
and durable binding records; never accept this context from model/tool input.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from verify_session_sandbox_binding import SessionBindingRouter


@dataclass(frozen=True)
class TrustedExecutionContext:
    session_id: str
    run_id: str
    isolation_scope: str
    lease_generation: int


class CubeE2BSessionAdapter:
    """Uses only public E2B Sandbox.connect / files / commands operations."""

    def __init__(self, bindings: SessionBindingRouter, *, sandbox_class=None):
        self.bindings = bindings
        if sandbox_class is None:
            from e2b import Sandbox
            sandbox_class = Sandbox
        self.sandbox_class = sandbox_class

    def _connect(self, ctx: TrustedExecutionContext):
        sandbox_id = self.bindings.route(
            session_id=ctx.session_id,
            run_id=ctx.run_id,
            isolation_scope=ctx.isolation_scope,
            lease_generation=ctx.lease_generation,
        )
        # A resolved Sandbox ID is not an auth token; Cube credentials and
        # server-side authorization still apply on the actual connection.
        return self.sandbox_class.connect(sandbox_id)

    @staticmethod
    def _path(relative_path: str) -> str:
        if not relative_path or not isinstance(relative_path, str):
            raise ValueError("Missing workspace path")
        path = PurePosixPath(relative_path)
        if (path.is_absolute() or relative_path.startswith("./") or
                any(segment in (".", "..") for segment in relative_path.split("/")) or
                "\\" in relative_path):
            raise ValueError("Path outside logical workspace is not allowed")
        return str(PurePosixPath("/workspace") / path)

    def execute(self, ctx: TrustedExecutionContext, command: str):
        if not command or not isinstance(command, str):
            raise ValueError("Expected nonempty remote command")
        return self._connect(ctx).commands.run(command)

    def read(self, ctx: TrustedExecutionContext, path: str):
        safe = self._path(path)
        return self._connect(ctx).files.read(safe)

    def write(self, ctx: TrustedExecutionContext, path: str, content: str):
        safe = self._path(path)
        return self._connect(ctx).files.write(safe, content)
