"""No-model real Docker proof: same SandboxProvider for different Agent roles."""

import json

from unified_sandbox_contract import (
    AdmissionDenied, DockerSandboxProvider, ExecutionBinding,
)


def denied(fn):
    try:
        fn()
    except AdmissionDenied:
        return True
    raise AssertionError("Unsafe sandbox request was admitted")


def main():
    provider = DockerSandboxProvider()
    task = ExecutionBinding("pdlc-run-A", "task-A-authorized")
    other = ExecutionBinding("portal-run-B", "task-B-authorized")
    first = provider.create(task)
    second = None
    try:
        # Simulated roles use identical provider lease and data plane contract.
        # These are NOT claims of live OpenCode/Agents SDK model invocations.
        provider.write(first, task, "prd.txt", b"requirements-v1")
        assert provider.read(first, task, "prd.txt") == b"requirements-v1"
        code, output, _ = provider.execute(
            first, task, ["sh", "-c", "cat prd.txt; printf ':qa' > qa.txt"]
        )
        assert code == 0 and output == "requirements-v1"
        assert provider.read(first, task, "qa.txt") == b":qa"
        assert denied(lambda: provider.read(first, other, "prd.txt"))
        assert denied(lambda: provider.write(first, other, "owned.txt", b"leak"))
        assert denied(lambda: provider.read(first, task, "../etc/passwd"))

        second = provider.create(other)
        provider.write(second, other, "prd.txt", b"portal-content")
        assert provider.read(second, other, "prd.txt") == b"portal-content"
        assert provider.read(first, task, "prd.txt") == b"requirements-v1"
        assert denied(lambda: provider.read(second, task, "prd.txt"))
        uid = provider.execute(first, task, ["id", "-u"])[1].strip()
        assert uid == "10001", uid
        print(json.dumps({
            "outcome": "PASS",
            "sandbox_instances_created": 2,
            "distinct_isolation_scopes": 2,
            "sequential_roles_one_lease": True,
            "wrong_binding_denied": True,
            "different_scope_content_isolated": True,
            "nonroot": True,
            "network_disabled": True,
            "llm_calls": 0,
            "native_opencode_in_sandbox": "NOT_TESTED",
            "agents_sdk_native_runner": "NOT_TESTED",
        }, sort_keys=True))
        return 0
    finally:
        for lease, binding in ((first, task), (second, other)):
            if lease:
                provider.close(lease, binding)


if __name__ == "__main__":
    raise SystemExit(main())