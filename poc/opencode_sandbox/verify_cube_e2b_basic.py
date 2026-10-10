"""Official E2B Python SDK minimum Cube conformance (no OpenAI dependency).

Offline mode never creates a Sandbox. --live requires an explicit Cube endpoint,
a template and CUBE_E2B_LIVE_CONFIRM=1. Test status is scoped to the exact SDK.
No model calls and no SDK internals/monkey patches are used.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from urllib.request import urlopen

from verify_cube_e2b import configuration


def emit(**data):
    print(json.dumps(data, ensure_ascii=False, sort_keys=True), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    config, reason = configuration()
    try:
        from e2b import Sandbox
        version = importlib.metadata.version("e2b")
    except (ImportError, importlib.metadata.PackageNotFoundError):
        emit(outcome="BLOCKED", reason="official e2b Python SDK not installed")
        return 2
    if not args.live:
        emit(outcome="PASS", scope="offline_config_only", sdk_version=version,
             cube_live="NOT_RUN", configured=bool(config), blocked=reason)
        return 0
    if reason or os.environ.get("CUBE_E2B_LIVE_CONFIRM") != "1":
        emit(outcome="BLOCKED", scope="live_cube",
             reason=reason or "explicit CUBE_E2B_LIVE_CONFIRM=1 required")
        return 2
    if config["url"].startswith("http://127.0.0.1:") or config["url"].startswith("http://localhost:"):
        for port, path in ((3000, "/health"), (8090, "/health"),
                           (9091, "/admin/v1/health")):
            try:
                with urlopen(f"http://127.0.0.1:{port}{path}", timeout=3) as resp:
                    if resp.status != 200:
                        raise RuntimeError("unhealthy")
            except Exception:
                emit(outcome="BLOCKED", scope="live_cube", dependency_port=port)
                return 2
    os.environ["E2B_API_URL"] = config["url"]
    os.environ["E2B_API_KEY"] = config["key"]
    sb = None
    stage = "create"
    try:
        sb = Sandbox.create(template=config["template"], timeout=120)
        # Prevent a synthetic debug handle from being mistaken for real Cube.
        if not sb.sandbox_id or sb.sandbox_id == "debug_sandbox_id":
            raise AssertionError("SDK returned missing/synthetic debug sandbox")
        stage = "files"
        name = "/tmp/ahp-e2b-conformance.txt"
        sb.files.write(name, "cube-sdk-probe")
        assert sb.files.read(name) == "cube-sdk-probe"
        stage = "commands"
        assert "cube-sdk-probe" in sb.commands.run("cat " + name).stdout
        emit(outcome="PASS", scope="live_cube_official_e2b",
             sdk_version=version, sandbox_id=sb.sandbox_id,
             files="PASS", commands="PASS", model_calls=0,
             openai_native_client="NOT_TESTED")
        return 0
    except Exception as exc:
        emit(outcome="FAIL", scope="live_cube_official_e2b", sdk_version=version,
             failed_stage=stage, create_returned_real_handle=bool(sb is not None and sb.sandbox_id != "debug_sandbox_id"),
             failed_type=type(exc).__name__,
             # Never emit exception string which may contain auth/header/URL.
             model_calls=0)
        return 1
    finally:
        if sb is not None and sb.sandbox_id != "debug_sandbox_id":
            sb.kill()


if __name__ == "__main__":
    raise SystemExit(main())
