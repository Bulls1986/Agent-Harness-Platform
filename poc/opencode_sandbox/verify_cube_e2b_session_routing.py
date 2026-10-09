"""Offline contract: one logical Runtime routes 2 Sessions to 2 E2B sandboxes.

An in-memory E2B stub verifies the PUBLIC SDK call shape without pretending
to exercise Cube's actual Control/Data Plane. No model, Docker or network.
"""

import json

from cube_e2b_session_adapter import CubeE2BSessionAdapter, TrustedExecutionContext
from verify_session_sandbox_binding import Binding, BindingDenied, SessionBindingRouter


class FakeE2BSandbox:
    existing = {}
    connects = []

    def __init__(self, sandbox_id):
        self.sandbox_id = sandbox_id
        self.disk = {}
        self.commands = FakeCommands(self)
        self.files = FakeFiles(self)

    @classmethod
    def connect(cls, sandbox_id):
        cls.connects.append(sandbox_id)
        return cls.existing[sandbox_id]


class FakeCommands:
    def __init__(self, sandbox):
        self.sandbox = sandbox

    def run(self, command):
        return type("Result", (), {"stdout": self.sandbox.sandbox_id + ":" + command})()


class FakeFiles:
    def __init__(self, sandbox):
        self.sandbox = sandbox

    def write(self, path, content):
        self.sandbox.disk[path] = content

    def read(self, path):
        return self.sandbox.disk[path]


def denied(call):
    try:
        call()
    except (BindingDenied, ValueError):
        return
    raise AssertionError("Unsafe routing operation admitted")


def main():
    FakeE2BSandbox.existing.clear()
    FakeE2BSandbox.connects.clear()
    for sandbox_id in ("cube-001", "cube-002"):
        FakeE2BSandbox.existing[sandbox_id] = FakeE2BSandbox(sandbox_id)

    # These are pre-existing Cube IDs supplied by the external SandboxProvider;
    # binding the logical Session does not create another process or Sandbox.
    router = SessionBindingRouter()
    router.bind(Binding("session-A", "run-A", "scope-A", "cube-001", 1))
    router.bind(Binding("session-B", "run-B", "scope-B", "cube-002", 1))
    adapter = CubeE2BSessionAdapter(router, sandbox_class=FakeE2BSandbox)
    a = TrustedExecutionContext("session-A", "run-A", "scope-A", 1)
    b = TrustedExecutionContext("session-B", "run-B", "scope-B", 1)

    adapter.write(a, "output.txt", "A-only")
    adapter.write(b, "output.txt", "B-only")
    assert adapter.read(a, "output.txt") == "A-only"
    assert adapter.read(b, "output.txt") == "B-only"
    assert adapter.execute(a, "echo hello").stdout == "cube-001:echo hello"
    assert adapter.execute(b, "echo hello").stdout == "cube-002:echo hello"

    before = len(FakeE2BSandbox.connects)
    denied(lambda: adapter.execute(TrustedExecutionContext("session-A", "run-B", "scope-A", 1), "id"))
    denied(lambda: adapter.read(TrustedExecutionContext("session-A", "run-A", "scope-A", 2), "output.txt"))
    denied(lambda: adapter.execute(TrustedExecutionContext("missing", "run-A", "scope-A", 1), "id"))
    denied(lambda: adapter.read(a, "../outside"))
    denied(lambda: adapter.write(a, "/etc/passwd", "unsafe"))
    assert len(FakeE2BSandbox.connects) == before, "Denied operation contacted E2B"

    # Worker restart: rehydrate platform binding records into a new adapter;
    # E2B reconnect targets the SAME already existing Sandbox ID.
    recovered = SessionBindingRouter()
    recovered.bind(Binding("session-A", "run-A", "scope-A", "cube-001", 1))
    restarted = CubeE2BSessionAdapter(recovered, sandbox_class=FakeE2BSandbox)
    assert restarted.read(a, "output.txt") == "A-only"
    assert len(FakeE2BSandbox.existing) == 2
    print(json.dumps({
        "outcome": "PASS", "scope": "offline_mocked_e2b_client_only",
        "shared_logical_runtime_instances": 1,
        "sessions": 2, "existing_sandbox_ids": 2,
        "e2b_connect_per_session": True, "e2b_commands_files_routed": True,
        "unauthorized_requests_rejected_before_connect": True,
        "same_sandbox_id_after_router_rehydrate": True,
        "new_sandbox_instances_created": 0, "model_calls": 0,
        "opencode_native_tool_hooked": False, "cube_live": "NOT_TESTED",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())