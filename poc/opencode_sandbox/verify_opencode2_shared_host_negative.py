"""Negative control: a Session ID/Location does NOT bind OpenCode v2 shell to a remote sandbox.

Uses three isolated, network-disabled Docker containers:
  one OpenCode 2 shared Host, and two simulated external Sandbox leases.
The test intentionally exercises an unadapted PUBLIC v2 shell endpoint.
It is not a test of Cube or a working remote tool adapter.
"""

import base64
import json
import re
import secrets
import time
from urllib.parse import urlencode

from unified_sandbox_contract import (
    DockerSandboxProvider,
    ExecutionBinding,
)
from session_sandbox_router import SessionSandboxRouter

IMAGE = ("ghcr.io/anomalyco/opencode@sha256:"
         "9500f3474188a4b89e165c65fada370dbde5e038cc3b751ed5dcbd27d7620315")


def main():
    provider = DockerSandboxProvider()
    binds = {
        "host": ExecutionBinding("shared-runtime", "host-not-tool-sandbox"),
        "a": ExecutionBinding("task-A", "scope-A"),
        "b": ExecutionBinding("task-B", "scope-B"),
    }
    leases = {}
    marker = "unadapted-" + secrets.token_hex(4)
    try:
        provider.image = IMAGE
        leases["host"] = provider.create(binds["host"])
        provider.image = "postgres:16-alpine"
        for key in ("a", "b"):
            leases[key] = provider.create(binds[key])
            provider.write(leases[key], binds[key], "identity.txt", key.encode())

        host, host_binding = leases["host"], binds["host"]
        rc, _, stderr = provider.execute(
            host, host_binding,
            ["sh", "-c", "mkdir -p /workspace/a /workspace/b; "
             "export HOME=/workspace XDG_DATA_HOME=/workspace/.local/share "
             "XDG_CACHE_HOME=/workspace/.cache XDG_CONFIG_HOME=/workspace/.config; "
             "nohup opencode serve --hostname 127.0.0.1 --port 4096 "
             "> /workspace/server.log 2>&1 < /dev/null &"],
        )
        assert rc == 0, stderr[:100]
        password = None
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            _, output, _ = provider.execute(
                host, host_binding,
                ["sh", "-c", "cat /workspace/server.log 2>/dev/null || true"],
            )
            result = re.search(r"server password\s+(\S+)", output)
            if result:
                password = result.group(1)
                break
            time.sleep(0.3)
        assert password, "OpenCode 2 did not start"
        auth = base64.b64encode(("opencode:" + password).encode()).decode()

        def request(path, payload=None):
            argv = ["wget", "-q", "-O", "-",
                    "--header=Authorization: Basic " + auth]
            if payload is not None:
                argv += ["--header=Content-Type: application/json",
                         "--post-data=" + json.dumps(payload, separators=(",", ":"))]
            return provider.execute(host, host_binding, argv +
                                    ["http://127.0.0.1:4096" + path], timeout=15)

        sessions = {}
        for key in ("a", "b"):
            rc, body, error = request("/api/session",
                {"location": {"directory": "/workspace/" + key}})
            assert rc == 0, error[:150]
            sessions[key] = json.loads(body)["data"]["id"]
        assert sessions["a"] != sessions["b"]

        for key in ("a", "b"):
            # Explicit V2 Location only. This API is NOT wired to the external
            # Cube/E2B Sandbox; the negative control should expose that fact.
            path = "/api/shell?" + urlencode({"location[directory]": "/workspace/" + key})
            rc, _, stderr = request(path, {
                "command": "printf " + marker + " > /workspace/" + key + "/marker.txt",
                "cwd": "/workspace/" + key, "timeout": 15000, "metadata": {},
            })
            assert rc == 0, "Native v2 shell failed: " + stderr[:180]

        for key in ("a", "b"):
            for _ in range(16):
                rc, body, _ = provider.execute(
                    host, host_binding,
                    ["sh", "-c", "cat /workspace/" + key + "/marker.txt 2>/dev/null"],
                )
                if rc == 0 and body == marker:
                    break
                time.sleep(0.15)
            assert body == marker, "Native v2 shell did not write into Host"
            rc, _, _ = provider.execute(
                leases[key], binds[key],
                ["sh", "-c", "test -e /workspace/marker.txt"],
            )
            assert rc != 0, "Unexpected mutation of independent Sandbox"
            assert provider.read(leases[key], binds[key], "identity.txt") == key.encode()

        # Positive CONTROL: a platform-routed executor can correctly resolve
        # Session A/B into distinct existing Sandbox leases without launching
        # a second OpenCode process. This does NOT hook native v2 APIs.
        routed = SessionSandboxRouter(provider)
        for key in ("a", "b"):
            routed.bind(sessions[key], binds[key], leases[key])
            exit_code, _, _ = routed.execute(
                sessions[key], binds[key],
                ["sh", "-c", "printf routed-" + key + " > /workspace/routed.txt"],
            )
            assert exit_code == 0
        for key in ("a", "b"):
            assert routed.read(sessions[key], binds[key], "routed.txt") == (
                "routed-" + key
            ).encode()
        try:
            routed.read(sessions["a"], binds["b"], "routed.txt")
        except Exception as exc:
            assert type(exc).__name__ == "AdmissionDenied"
        else:
            raise AssertionError("Cross-session authorization unexpectedly permitted")
        host_rc, _, _ = provider.execute(
            host, host_binding, ["sh", "-c", "test -e /workspace/routed.txt"]
        )
        assert host_rc != 0

        print(json.dumps({
            "outcome": "PASS_EXPECTED_NEGATIVE",
            "shared_opencode_host_instances": 1,
            "logical_sessions": 2,
            "simulated_external_sandboxes": 2,
            "host_native_shell_executed_in_host": True,
            "per_session_remote_sandbox_routing": False,
            "native_shell_api_requires_separate_isolation_strategy": True,
            "platform_routed_execute_isolated": True,
            "platform_routed_read_isolated": True,
            "cross_binding_rejected": True,
            "native_opencode_tools_hooked": False,
            "model_calls": 0,
            "cube_integration": "NOT_TESTED",
        }, sort_keys=True))
        return 0
    finally:
        for key in ("b", "a", "host"):
            if key in leases:
                provider.close(leases[key], binds[key])


if __name__ == "__main__":
    raise SystemExit(main())
