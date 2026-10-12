"""Read-only, REAL Cube MicroVM Guest preflight for DEV-M5 1.3.

This is NOT a claim that OpenCode has been integrated. It creates one
short-lived synthetic native sandbox, checks a fixed allowlist of command
prerequisites *inside the guest*, and always destroys the sandbox. It never
launches Host Shell or accepts arbitrary tool commands from an API caller.
"""
from __future__ import annotations

import json
import os
from uuid import uuid4


REQUIRED = ("sh", "git", "opencode")
OPTIONAL = ("node", "npm")


def check_prerequisites(guest) -> dict[str, bool]:
    result: dict[str, bool] = {}
    for name in REQUIRED + OPTIONAL:
        # Static, developer-maintained lookup only, never request-supplied.
        lookup = guest.commands.run("command -v " + name, timeout=12)
        result[name] = (
            lookup.exit_code == 0 and bool(lookup.stdout.strip()))
    # OpenCode also ships standalone binaries without a separately exposed
    # node/npm command. Probe the REAL program rather than infer readiness
    # from an unrelated host package manager.
    version = guest.commands.run("opencode --version", timeout=15) if (
        result["opencode"]) else None
    result["opencode_version_works"] = (
        version is not None
        and version.exit_code == 0
        and bool(version.stdout.strip()))
    return result


def main() -> int:
    if not all(os.environ.get(name) for name in (
            "CUBE_API_URL", "CUBE_TEMPLATE_ID")):
        raise RuntimeError("REAL_GUEST_GATE_NOT_RUN: Cube endpoint/template missing")
    from cubesandbox import Sandbox

    sandbox = None
    destroyed = False
    try:
        sandbox = Sandbox.create(
            template=os.environ["CUBE_TEMPLATE_ID"], timeout=240,
            allow_internet_access=False,
            metadata={"purpose": "synthetic-opencode-prerequisite",
                      "probe": uuid4().hex},
        )
        result = check_prerequisites(sandbox)
        ready = all(result[name] for name in REQUIRED) and result[
            "opencode_version_works"]
        print(json.dumps({"gate": "DEV-M5-1.3-GUEST-PREFLIGHT",
                          "sandbox_id": sandbox.sandbox_id,
                          "prerequisites": result,
                          "opencode_runtime_ready": ready},
                         sort_keys=True), flush=True)
    finally:
        if sandbox is not None:
            sandbox.kill()
            destroyed = True
            print("NATIVE_GUEST_PREFLIGHT_DESTROY_ACK", flush=True)
    if not destroyed:
        raise RuntimeError("Cube sandbox lifecycle was not verified")
    return 0 if ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
