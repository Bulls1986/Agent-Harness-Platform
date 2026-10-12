"""DEV-M5 GENUINE CubeSandbox MicroVM smoke. Never uses Fake Transport.

Requires an actual, already running CubeSandbox CubeAPI/Proxy and READY
native template. Only proves CREATE / Guest files / NEW SDK CONNECT /
unchanged bytes / destroy. Full HC-03 PG/worker/capability gates are separate.
"""
from __future__ import annotations

import json
import os
import uuid

def verify() -> dict[str, object]:
    missing = [k for k in ("CUBE_API_URL", "CUBE_TEMPLATE_ID") if not os.getenv(k)]
    if missing:
        raise RuntimeError("REAL_CUBE_NOT_CONFIGURED: " + ",".join(missing))

    from cubesandbox import Sandbox

    tag = "harness-cube-smoke-" + uuid.uuid4().hex[:12]
    sandbox = None
    destroyed = False
    try:
        sandbox = Sandbox.create(
            template=os.environ["CUBE_TEMPLATE_ID"],
            timeout=300,
            metadata={"harness_smoke": tag, "purpose": "native_workspace_continuity"},
        )
        native_id = sandbox.sandbox_id
        if not native_id:
            raise RuntimeError("Cube did not return a real Sandbox ID")
        print("NATIVE_CUBE_CREATED", native_id, flush=True)
        path = "/tmp/" + tag + ".txt"
        original = "native-microvm-" + uuid.uuid4().hex
        sandbox.files.write(path, original)
        if sandbox.files.read(path) != original:
            raise RuntimeError("Initial native Guest file read/write mismatch")
        print("NATIVE_GUEST_FILE_OK", flush=True)

        # Never replay create(). The second SDK connection must use exactly
        # the same provider id and see the original guest's existing bytes.
        reconnected = Sandbox.connect(native_id)
        if reconnected.sandbox_id != native_id:
            raise RuntimeError("Native reconnect changed Sandbox identity")
        if reconnected.files.read(path) != original:
            raise RuntimeError("New native connection lost original guest file")
        print("NATIVE_CONNECT_ORIGINAL_BYTES_OK", flush=True)

        # Actual provider destroy ACK, not a simulated Harness state.
        reconnected.kill()
        destroyed = True
        return {
            "outcome": "PASS_REAL_CUBE_MICROVM_MINIMAL",
            "sandbox_id": native_id,
            "guest_read_write": "PASS",
            "same_provider_id_reconnect": "PASS",
            "original_bytes_preserved": "PASS",
            "destroy_ack": "PASS",
            "harness_pg_binding": "NOT_TESTED",
            "physical_worker_A_to_B": "NOT_TESTED",
            "guest_fencing": "NOT_TESTED",
        }
    finally:
        if sandbox is not None and not destroyed:
            try:
                sandbox.kill()
                print("NATIVE_CUBE_CLEANUP_OK", flush=True)
            except Exception:
                print("NATIVE_CUBE_CLEANUP_ACK_UNKNOWN: manual reconciliation required", flush=True)


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True), flush=True)
