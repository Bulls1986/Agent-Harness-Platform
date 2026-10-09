"""Public OpenAI Agents SDK function_tool -> platform SandboxProvider bridge.

An optional adapter when SDK-native SandboxSession interoperability is not
available. The platform owns sandbox admission; SDK owns its model/agent loop.
This does not monkey-patch SDK internals or start an Agent process per session.
"""

from __future__ import annotations

from unified_sandbox_contract import (
    DockerSandboxProvider, ExecutionBinding, SandboxLease,
)


def sandbox_tools(provider: DockerSandboxProvider,
                  binding: ExecutionBinding, lease: SandboxLease):
    """Return SDK function tools scoped to an existing approved sandbox.

    Importing the SDK is deferred; absence of SDK is an explicit capability
    gap, not permission to run user commands in the host process.
    """
    from agents import function_tool

    @function_tool
    def sandbox_shell(command: str) -> str:
        """Execute a shell command within the approved sandbox workspace."""
        exit_code, stdout, stderr = provider.execute(
            lease, binding, ["sh", "-c", command], timeout=12,
        )
        return f"exit={exit_code}\nstdout={stdout}\nstderr={stderr}"

    @function_tool
    def sandbox_read(name: str) -> str:
        """Read one named workspace file from the approved sandbox."""
        return provider.read(lease, binding, name).decode(errors="replace")

    @function_tool
    def sandbox_write(name: str, content: str) -> str:
        """Write one named workspace file in the approved sandbox."""
        provider.write(lease, binding, name, content.encode())
        return "written"

    return [sandbox_shell, sandbox_read, sandbox_write]