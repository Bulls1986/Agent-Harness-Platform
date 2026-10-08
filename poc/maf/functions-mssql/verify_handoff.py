"""Real local Functions+MSSQL provider handoff test; aborts on ambiguity.

Requirements: started Azure Functions host, SQL Server and Azurite. No LLM.
Never infers MSSQL backend solely from host.json: inspect DB/log evidence.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import time
from urllib import request, error

BASE = "http://127.0.0.1:17071"
ROOT = Path(__file__).resolve().parent
COMPOSE = ROOT.parent / "compose-functions-mssql.yml"
ENVFILE = ROOT / ".env.local"
MARKERS = ROOT / "markers"
ROUTE = "/api/workflow/maf_mssql_poc_hitl"
# Each invocation retains previous Run/History evidence and creates fresh fixtures.
_NONCE = os.urandom(6).hex()
APPROVED_CASE = "approved-fixture-" + _NONCE
REJECTED_CASE = "rejected-fixture-" + _NONCE


def invoke(method: str, url: str, payload=None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(BASE + url, data=body, method=method,
                          headers={"Content-Type": "application/json"})
    try:
        with request.urlopen(req, timeout=12) as resp:
            data = resp.read().decode()
            return json.loads(data) if data else {}
    except error.HTTPError as exc:
        raise RuntimeError(
            f"{method} {url}: HTTP {exc.code} {exc.read(2000)!r}"
        ) from exc


def compose(*args: str) -> str:
    command = ["docker", "compose", "-p", "maf-mssql-poc",
               "--env-file", str(ENVFILE), "-f", str(COMPOSE), *args]
    return subprocess.check_output(command, text=True, stderr=subprocess.STDOUT).strip()


def wait_for_host(seconds: int = 90):
    end = time.monotonic() + seconds
    last = None
    while time.monotonic() < end:
        try:
            reply = invoke("GET", "/api/health")
            print("Functions health:", reply)
            return
        except Exception as exc:
            last = str(exc)
            time.sleep(2)
    raise TimeoutError(f"Functions host not healthy: {last}")


def pending(instance: str, seconds: int = 90):
    until = time.monotonic() + seconds
    last = None
    while time.monotonic() < until:
        value = invoke("GET", f"{ROUTE}/status/{instance}")
        last = value
        requests = value.get("pendingHumanInputRequests") or value.get("pending_human_input_requests") or []
        if requests:
            if len(requests) != 1:
                raise RuntimeError(f"Unexpected native pending requests: {requests!r}")
            req = requests[0]
            req_id = req.get("requestId") or req.get("request_id")
            if not req_id:
                raise RuntimeError(f"Missing native request ID: {req!r}")
            return req_id
        if str(value.get("runtimeStatus", "")).lower() in ("completed", "failed", "terminated"):
            raise RuntimeError(f"Instance terminal before HITL: {value!r}")
        time.sleep(2)
    raise TimeoutError(f"No pending request: {last!r}")


def count(case: str, phase: str) -> int:
    path = MARKERS / f"{case}.{phase}"
    return len(path.read_text().splitlines()) if path.exists() else 0


def main():
    if not ENVFILE.exists():
        raise RuntimeError("Missing local untracked .env.local")
    for case in (APPROVED_CASE, REJECTED_CASE):
        if count(case, "prepare") or count(case, "action"):
            raise RuntimeError("Expected fresh marker directory; never reuse prior POC data")
    wait_for_host()
    ids = {}
    for case in (APPROVED_CASE, REJECTED_CASE):
        started = invoke("POST", f"{ROUTE}/run", case)
        instance = started.get("instanceId") or started.get("instance_id")
        if not instance:
            raise RuntimeError(f"No native durable instance ID: {started!r}")
        ids[case] = (instance, pending(instance))
    for case in ids:
        if count(case, "prepare") != 1 or count(case, "action") != 0:
            raise AssertionError(f"Pre-restart side effect anomaly for {case}")
    worker_a = compose("ps", "-q", "functions")
    if not worker_a:
        raise RuntimeError("No worker container")
    # Deliberately crash Worker A, not a graceful Docker restart.
    # MSSQL TaskHub and Azurite containers remain untouched.
    subprocess.check_call(["docker", "kill", "--signal", "KILL", worker_a])
    compose("up", "-d", "--force-recreate", "--no-deps", "functions")
    worker_b = compose("ps", "-q", "functions")
    if worker_a == worker_b:
        raise AssertionError("Worker was not replaced")
    wait_for_host(150)
    for case, (instance, expected_req) in ids.items():
        actual_req = pending(instance, 90)
        if actual_req != expected_req:
            raise AssertionError("Native request identity changed across Worker replacement")
        decision = "APPROVED" if case == APPROVED_CASE else "REJECTED"
        invoke("POST", f"{ROUTE}/respond/{instance}/{actual_req}", decision)
    for case, (instance, _) in ids.items():
        end = time.monotonic() + 120
        while time.monotonic() < end:
            s = invoke("GET", f"{ROUTE}/status/{instance}")
            status = str(s.get("runtimeStatus", "")).lower()
            if status in ("completed", "failed", "terminated"):
                if status != "completed":
                    raise AssertionError(f"Durable instance {case} failed: {s!r}")
                expected = ["SIMULATED_EXECUTION:" + case] if case == APPROVED_CASE else ["DENIED_NO_EXECUTION"]
                if s.get("output") != expected:
                    raise AssertionError(f"Unexpected native output: {s.get('output')!r}; expected {expected!r}")
                break
            time.sleep(2)
        else:
            raise TimeoutError(f"Instance did not complete: {instance}")
    assert count(APPROVED_CASE, "prepare") == 1
    assert count(REJECTED_CASE, "prepare") == 1
    assert count(APPROVED_CASE, "action") == 1
    assert count(REJECTED_CASE, "action") == 0
    print(json.dumps({"provider": "mssql-required-external-verification",
                      "old_worker": worker_a[:12], "new_worker": worker_b[:12],
                      "native_hitl": "PASS", "completed_prepare_replay": 0,
                      "simulated_approval_action": 1, "rejected_action": 0}))


if __name__ == "__main__":
    main()
