"""Bounded platform SandboxProvider proof. NOT a production sandbox service.

This is a minimal provider-side execution boundary for *multiple* Harness
clients.  It does not replace native Agents SDK sandbox clients or CubeMaster.
No agent model, credential, or OpenCode process is launched here.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import secrets
import subprocess


@dataclass(frozen=True)
class ExecutionBinding:
    run_id: str
    isolation_scope: str  # An approved task/workspace security scope, NOT projectID.


@dataclass(frozen=True)
class SandboxLease:
    id: str
    binding: ExecutionBinding


class AdmissionDenied(Exception):
    pass


class DockerSandboxProvider:
    """Disposable Docker fallback adapter; no runtime-owned session process.

    Each leased container has isolated temporary filesystem/OS process scope.
    Reusing a lease across professional Agents is permitted only for the same
    frozen binding, and only when upstream Policy allows sequential reuse.
    """

    def __init__(self, image: str = "postgres:16-alpine"):
        self.image = image
        self._active: dict[str, tuple[SandboxLease, str]] = {}

    @staticmethod
    def _docker(*argv: str, input: bytes | None = None, timeout: float = 20):
        return subprocess.run(
            ["docker", *argv], input=input, capture_output=True,
            timeout=timeout, check=False,
        )

    @staticmethod
    def _file(name: str):
        # Intentionally limited to one flat workspace file in this POC.
        # Never trust a user-supplied path with .., /, symlinks or abs paths.
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,80}", name) or name in (".", ".."):
            raise AdmissionDenied("Invalid sandbox file name")
        return f"/workspace/{name}"

    def create(self, binding: ExecutionBinding) -> SandboxLease:
        if not binding.run_id or not binding.isolation_scope:
            raise AdmissionDenied("Missing execution binding")
        result = self._docker(
            "run", "--detach", "--rm", "--pull=never",
            "--label", "ahp.sandbox.poc=true",
            "--network", "none", "--read-only",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--pids-limit", "64", "--memory", "128m", "--cpus", "0.5",
            "--tmpfs", "/workspace:rw,nosuid,nodev,size=16m,mode=1777",
            "--user", "10001:10001", "--entrypoint", "sh",
            self.image, "-c", "sleep 180",
            timeout=30,
        )
        if result.returncode:
            raise RuntimeError("Docker Sandbox start rejected")
        container = result.stdout.decode().strip()
        lease = SandboxLease(secrets.token_hex(16), binding)
        self._active[lease.id] = (lease, container)
        return lease

    def _get(self, lease: SandboxLease, binding: ExecutionBinding) -> str:
        item = self._active.get(lease.id)
        if item is None or item[0] != lease or lease.binding != binding:
            raise AdmissionDenied("Sandbox binding mismatch or released lease")
        return item[1]

    def execute(self, lease: SandboxLease, binding: ExecutionBinding,
                argv: list[str], *, timeout: float = 10) -> tuple[int, str, str]:
        container = self._get(lease, binding)
        if not argv or not all(isinstance(part, str) for part in argv):
            raise AdmissionDenied("Command requires argv")
        result = self._docker(
            "exec", "--workdir", "/workspace", container, *argv,
            timeout=min(timeout, 30),
        )
        return (result.returncode,
                result.stdout[:16_384].decode(errors="replace"),
                result.stderr[:16_384].decode(errors="replace"))

    def write(self, lease: SandboxLease, binding: ExecutionBinding,
              name: str, content: bytes) -> None:
        container = self._get(lease, binding)
        path = self._file(name)
        if len(content) > 1024 * 1024:
            raise AdmissionDenied("POC payload exceeds maximum")
        result = self._docker(
            "exec", "-i", "--workdir", "/workspace", container,
            "sh", "-c", 'cat > "$1"', "sh", path, input=content,
        )
        if result.returncode:
            raise RuntimeError("Sandbox write failed")

    def read(self, lease: SandboxLease, binding: ExecutionBinding, name: str) -> bytes:
        container = self._get(lease, binding)
        path = self._file(name)
        result = self._docker("exec", container, "cat", path)
        if result.returncode:
            raise FileNotFoundError("Sandbox file unavailable")
        return result.stdout

    def close(self, lease: SandboxLease, binding: ExecutionBinding) -> None:
        container = self._get(lease, binding)
        try:
            result = self._docker("rm", "-f", container, timeout=20)
            if result.returncode:
                raise RuntimeError("Sandbox release failed")
        finally:
            self._active.pop(lease.id, None)