"""POC-only strict session -> SandboxLease router (NOT a production session store).

Uses the existing SandboxProvider public methods. Binding is only an identity
contract; the caller MUST route all execution through this adapter. Native
OpenCode 2 Host endpoints are NOT transparently captured by the registry.
"""

from dataclasses import dataclass

from unified_sandbox_contract import (
    AdmissionDenied, DockerSandboxProvider, ExecutionBinding, SandboxLease,
)


@dataclass(frozen=True)
class AssignedSandbox:
    binding: ExecutionBinding
    lease: SandboxLease


class SessionSandboxRouter:
    def __init__(self, provider: DockerSandboxProvider):
        self.provider = provider
        self._assigned: dict[str, AssignedSandbox] = {}

    def bind(self, session_id: str, binding: ExecutionBinding, lease: SandboxLease):
        if not session_id or session_id in self._assigned:
            raise AdmissionDenied("Missing or already assigned Session ID")
        if lease.binding != binding:
            raise AdmissionDenied("Session Sandbox binding mismatch")
        self._assigned[session_id] = AssignedSandbox(binding, lease)

    def _resolve(self, session_id: str, binding: ExecutionBinding):
        resolved = self._assigned.get(session_id)
        if resolved is None or resolved.binding != binding:
            raise AdmissionDenied("Session binding not authorized")
        return resolved.lease

    def execute(self, session_id: str, binding: ExecutionBinding, argv: list[str]):
        return self.provider.execute(self._resolve(session_id, binding), binding, argv)

    def read(self, session_id: str, binding: ExecutionBinding, filename: str):
        return self.provider.read(self._resolve(session_id, binding), binding, filename)

    def unbind(self, session_id: str, binding: ExecutionBinding):
        self._resolve(session_id, binding)
        del self._assigned[session_id]