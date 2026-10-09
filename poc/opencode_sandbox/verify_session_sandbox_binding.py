"""Platform-owned Session → Sandbox Lease contract (not OpenCode integration).

No model, network, Docker, or real Cube required. This POC only tests the
binding/admission semantics that are necessary but insufficient for safe
shared-Host execution. The durable store is NOT implemented by this fixture.
"""

from dataclasses import dataclass
import json


class BindingDenied(Exception):
    pass


@dataclass(frozen=True)
class Binding:
    session_id: str
    run_id: str
    isolation_scope: str
    sandbox_id: str
    lease_generation: int


class SessionBindingRouter:
    def __init__(self):
        self._data: dict[str, Binding] = {}

    def bind(self, binding: Binding):
        if (not all((binding.session_id, binding.run_id,
                     binding.isolation_scope, binding.sandbox_id))
                or binding.lease_generation < 1):
            raise BindingDenied("Invalid Sandbox binding")
        existing = self._data.get(binding.session_id)
        if existing and existing != binding:
            raise BindingDenied("Binding mutation requires fenced rebind workflow")
        if any(x.sandbox_id == binding.sandbox_id and
               x.isolation_scope != binding.isolation_scope
               for x in self._data.values()):
            raise BindingDenied("Same Sandbox across isolation scopes")
        self._data[binding.session_id] = binding

    def route(self, *, session_id: str, run_id: str,
              isolation_scope: str, lease_generation: int):
        # Never fall back to host execution when the binding is absent or stale.
        binding = self._data.get(session_id)
        if not binding or (binding.run_id, binding.isolation_scope,
                           binding.lease_generation) != (
                               run_id, isolation_scope, lease_generation):
            raise BindingDenied("Absent or stale Session Sandbox Lease")
        return binding.sandbox_id


def denied(callback):
    try:
        callback()
    except BindingDenied:
        return
    raise AssertionError("Expected Sandbox admission denial")


def main():
    router = SessionBindingRouter()
    a = Binding("session-A", "run-A", "scope-A", "cube-001", 1)
    b = Binding("session-B", "run-B", "scope-B", "cube-002", 1)
    router.bind(a)
    router.bind(b)
    assert router.route(session_id="session-A", run_id="run-A",
                        isolation_scope="scope-A", lease_generation=1) == "cube-001"
    assert router.route(session_id="session-B", run_id="run-B",
                        isolation_scope="scope-B", lease_generation=1) == "cube-002"
    # Idempotent rebind of the exact same platform record is safe.
    router.bind(a)
    denied(lambda: router.route(session_id="session-A", run_id="run-B",
                                isolation_scope="scope-A", lease_generation=1))
    denied(lambda: router.route(session_id="session-A", run_id="run-A",
                                isolation_scope="scope-A", lease_generation=2))
    denied(lambda: router.route(session_id="unknown", run_id="run-A",
                                isolation_scope="scope-A", lease_generation=1))
    denied(lambda: router.bind(Binding("session-A", "run-A", "scope-A", "cube-003", 2)))
    denied(lambda: router.bind(Binding("session-C", "run-C", "scope-C", "cube-001", 1)))
    print(json.dumps({
        "outcome": "PASS", "scope": "platform_binding_logic_only",
        "sessions": 2, "distinct_sandbox_ids": 2,
        "unknown_or_stale_binding_denied": True,
        "cross_scope_reuse_denied": True,
        "session_to_opencode_tool_routing": "NOT_TESTED",
        "cube_live": "NOT_TESTED",
    }, sort_keys=True))


if __name__ == "__main__":
    main()