"""Run deterministic, dependency-light, zero-model/zero-Cube admission preflight.

All subtests are explicitly OFFLINE. This is NOT an E2B or OpenCode live gate.
No sandbox, Docker container, external process server, or model API is created.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
CHECKS = (
    ("cube_native_config_only", "poc/opencode_sandbox/verify_cube_native_live.py", "offline_only"),
    ("session_scope_binding", "poc/opencode_sandbox/verify_session_sandbox_binding.py", "platform_binding_logic_only"),
    ("e2b_session_mock", "poc/opencode_sandbox/verify_cube_e2b_session_routing.py", "offline_mocked_e2b_client_only"),
)

def main() -> int:
    entries = []
    for name, path, expected_scope in CHECKS:
        run = subprocess.run(
            [sys.executable, "-B", str(ROOT / path)],
            cwd=ROOT, capture_output=True, text=True, timeout=25,
            env={k: v for k, v in __import__("os").environ.items()
                 if k not in ("CUBE_NATIVE_LIVE_CONFIRM", "CUBE_E2B_LIVE_CONFIRM")},
        )
        last = next((s for s in reversed(run.stdout.splitlines()) if s.strip()), "")
        try:
            data = json.loads(last)
            passed = run.returncode == 0 and data.get("outcome") == "PASS" and data.get("scope") == expected_scope
        except (ValueError, TypeError):
            passed = False
        entries.append({"name": name, "scope": expected_scope, "outcome": "PASS" if passed else "FAIL",
                        "returncode": run.returncode})
    result = "PASS_OFFLINE_ONLY" if all(x["outcome"] == "PASS" for x in entries) else "FAIL"
    print(json.dumps({
        "outcome": result, "checks": entries, "cube_live": "NOT_RUN",
        "openai_agent_loop": "NOT_RUN", "opencode2_cube": "NOT_RUN",
        "production_admission": "NOT_EVALUATED_BY_THIS_SCRIPT",
    }, ensure_ascii=False, sort_keys=True))
    return 0 if result == "PASS_OFFLINE_ONLY" else 1

if __name__ == "__main__":
    raise SystemExit(main())
