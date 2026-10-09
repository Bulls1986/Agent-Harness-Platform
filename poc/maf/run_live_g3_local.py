"""One-shot G3 live gate: isolated Docker PostgreSQL, real LiteLLM, cleanup.

Requires the three POC_LITELLM_* variables in the launching process (or
the current Windows user's Environment settings). Never accepts secrets via
CLI flags, prints their values, or persists them in the repository.
Run from repository root with pinned MAF Python environment.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path


def _prepare_config() -> list[str]:
    names = ("POC_LITELLM_API_KEY", "POC_LITELLM_BASE_URL", "POC_LITELLM_MODEL")
    # Windows HKCU variables set after WebCodex desktop launched are not
    # inherited by its already-running Runner; read the current user's
    # environment instead, so the desktop/Runner need not be restarted.
    if os.name == "nt":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                for name in names:
                    if not os.environ.get(name):
                        try:
                            value, _ = winreg.QueryValueEx(key, name)
                            if isinstance(value, str) and value:
                                os.environ[name] = value
                        except FileNotFoundError:
                            pass
        except FileNotFoundError:
            pass
    return [name for name in names if not os.environ.get(name)]


def _docker(*args: str, env: dict | None = None, timeout: int = 30) -> str:
    proc = subprocess.run(["docker", *args], env=env, capture_output=True,
                          text=True, timeout=timeout)
    if proc.returncode != 0:
        # Docker errors may contain secret-bearing command data: no raw stderr.
        raise RuntimeError("Disposable local Docker/PostgreSQL operation failed")
    return proc.stdout.strip()


def main() -> int:
    missing = _prepare_config()
    if missing:
        print(json.dumps({"outcome": "SETUP_GAP", "missing_environment": missing}))
        return 2
    if not (Path("poc") / "maf" / "verify_live_model_protocol.py").is_file():
        print(json.dumps({"outcome": "SETUP_GAP", "reason": "run_from_repository_root"}))
        return 2

    # Local disposable DB credentials generated fresh per run. Never in argv,
    # only in the Docker CLI process environment and child Python environment.
    pg_password = secrets.token_urlsafe(30)
    container = "maf-g3-live-" + secrets.token_hex(5)
    image = os.environ.get("POC_G3_POSTGRES_IMAGE", "postgres:16-alpine")
    env = os.environ.copy()
    env["POSTGRES_PASSWORD"] = pg_password
    started = False
    try:
        _docker("run", "-d", "--rm", "--name", container,
                "-e", "POSTGRES_USER=poc",
                "-e", "POSTGRES_DB=poc_g3_live",
                "-e", "POSTGRES_PASSWORD",
                "-p", "127.0.0.1::5432", image, env=env, timeout=70)
        started = True
        port_info = _docker("port", container, "5432/tcp")
        port_match = re.search(r":([0-9]+)\s*$", port_info)
        if port_match is None:
            raise RuntimeError("Unable to resolve test DB loopback port")
        port = int(port_match.group(1))
        for _ in range(50):
            result = subprocess.run(
                ["docker", "exec", container, "pg_isready", "-U", "poc",
                 "-d", "poc_g3_live"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=8,
            )
            if result.returncode == 0:
                break
            time.sleep(0.3)
        else:
            raise RuntimeError("Temporary PostgreSQL not ready")

        child_env = os.environ.copy()
        child_env["POC_POSTGRES_DSN"] = (
            f"postgresql://poc:{pg_password}@127.0.0.1:{port}/poc_g3_live"
        )
        result = subprocess.run(
            [sys.executable, "poc/maf/verify_live_model_protocol.py"],
            env=child_env, timeout=230,
        )
        return result.returncode
    except (RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
        print(json.dumps({"outcome": "GAP", "exception_type": type(exc).__name__}))
        return 1
    finally:
        # Attempt removal even after a partially failed Docker startup. Never
        # mutate the shared A34 PostgreSQL container.
        try:
            _docker("rm", "-f", container, timeout=25)
        except (OSError, subprocess.TimeoutExpired, RuntimeError):
            if started:
                print(json.dumps({"outcome": "CLEANUP_GAP", "resource": "ephemeral-postgres"}))


if __name__ == "__main__":
    raise SystemExit(main())
