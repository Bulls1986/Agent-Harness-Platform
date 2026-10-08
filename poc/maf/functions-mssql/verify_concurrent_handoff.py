"""A34: two concurrent identical Functions app replicas share MSSQL TaskHub.

Worker A is the sole worker when Prepare/approval waiting begins; Worker B
joins the SAME TaskHub while A is alive. SIGKILL A; B completes native HITL.
Only the separate maf-mssql-a34 project containers may be stopped/recreated.
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
import verify_handoff as v

PROJECT = "maf-mssql-a34"
COMPOSE = Path(__file__).resolve().parent.parent / "compose-functions-mssql-a34.yml"
ENVFILE = Path(__file__).resolve().parent / ".env.local"
A = "http://127.0.0.1:17081"
B = "http://127.0.0.1:17082"


def run(*args: str) -> str:
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT).strip()


def compose(*args: str) -> str:
    return run("docker", "compose", "-p", PROJECT,
               "--env-file", str(ENVFILE), "-f", str(COMPOSE), *args)


def container(service: str) -> str:
    cid = compose("ps", "-q", service)
    if not re.fullmatch(r"[a-f0-9]{12,64}", cid):
        raise AssertionError(f"Missing running {service}: {cid!r}")
    assert run("docker", "inspect", "-f", "{{.State.Running}}", cid) == "true"
    return cid


def provider_ready(cid: str) -> None:
    logs = run("docker", "logs", "--tail", "1600", cid)
    assert "Using the mssql storage provider." in logs, (
        f"MSSQL provider missing from {cid[:12]} logs"
    )
    assert "Task hub worker started." in logs


def wait_ready(port: str) -> None:
    v.BASE = port
    v.wait_for_host(150)


def db_count(instance_ids: list[str]) -> tuple[int, int]:
    if any(not re.fullmatch("[0-9a-f]{32}", item) for item in instance_ids):
        raise ValueError("Bad opaque instance identifier for DB audit")
    sql_ids = ",".join("'" + item + "'" for item in instance_ids)
    sql = (
        "SET NOCOUNT ON; "
        "SELECT COUNT(*) FROM dt.Instances "
        f"WHERE InstanceID IN ({sql_ids}) AND RuntimeStatus='Completed'; "
        f"SELECT COUNT(*) FROM dt.History WHERE InstanceID IN ({sql_ids});"
    )
    cmd = (
        "/opt/mssql-tools18/bin/sqlcmd -C -b -h -1 -W "
        '-S localhost -U sa -P "$MSSQL_SA_PASSWORD" '
        f'-d DurableA34 -Q "{sql}"'
    )
    output = run("docker", "exec", "maf-mssql-poc-mssql-1",
                 "/bin/bash", "-lc", cmd)
    numbers = [int(x.strip()) for x in output.splitlines()
               if x.strip().isdigit()]
    if len(numbers) != 2:
        raise AssertionError(f"Unexpected SQL audit response: {output[:300]!r}")
    return numbers[0], numbers[1]


def main() -> None:
    if not ENVFILE.exists():
        raise RuntimeError("Only local ignored .env.local may supply the SQL secret")
    cases = (v.APPROVED_CASE, v.REJECTED_CASE)
    for case in cases:
        assert v.count(case, "prepare") == 0 and v.count(case, "action") == 0
    # No pending runs from this isolated A34 test project may be in progress.
    compose("stop", "worker-b")
    compose("up", "-d", "--force-recreate", "--no-deps", "worker-a")
    a_id = container("worker-a")
    wait_ready(A)
    provider_ready(a_id)
    infra_before = (container_id("maf-mssql-poc-mssql-1"),
                    container_id("maf-mssql-poc-azurite-1"))
    created: dict[str, tuple[str, str]] = {}
    for case in cases:
        response = v.invoke("POST", f"{v.ROUTE}/run", case)
        instance = response.get("instanceId")
        assert instance and re.fullmatch("[0-9a-f]{32}", instance), response
        created[case] = instance, v.pending(instance, 95)
    assert all(v.count(case, "prepare") == 1 and
               v.count(case, "action") == 0 for case in cases)
    compose("up", "-d", "--force-recreate", "--no-deps", "worker-b")
    b_id = container("worker-b")
    assert a_id != b_id
    a_image = run("docker", "inspect", "-f", "{{.Image}}", a_id)
    b_image = run("docker", "inspect", "-f", "{{.Image}}", b_id)
    assert a_image and a_image == b_image, "Workers are not identical application image replicas"
    wait_ready(B)
    provider_ready(b_id)
    # Prove simultaneous workers and B reading A's native pending requests.
    assert container("worker-a") == a_id
    assert container("worker-b") == b_id
    for case, (instance, req_id) in created.items():
        assert v.pending(instance, 50) == req_id, "Second replica sees different request"
    run("docker", "kill", "--signal", "KILL", a_id)
    assert container("worker-b") == b_id
    assert (container_id("maf-mssql-poc-mssql-1"),
            container_id("maf-mssql-poc-azurite-1")) == infra_before
    for case, (instance, request_id) in created.items():
        assert v.pending(instance, 95) == request_id
        v.invoke("POST", f"{v.ROUTE}/respond/{instance}/{request_id}",
                 "APPROVED" if case == v.APPROVED_CASE else "REJECTED")
    for case, (instance, _) in created.items():
        expected = ["SIMULATED_EXECUTION:" + case] if case == v.APPROVED_CASE else ["DENIED_NO_EXECUTION"]
        for _ in range(70):
            status = v.invoke("GET", f"{v.ROUTE}/status/{instance}")
            if status.get("runtimeStatus") == "Completed":
                assert status.get("output") == expected, status
                break
            if status.get("runtimeStatus") in ("Failed", "Terminated"):
                raise AssertionError(f"Native Workflow failure: {case}")
            time.sleep(2)
        else:
            raise TimeoutError(f"Workflow not completed: {case}")
    assert v.count(v.APPROVED_CASE, "prepare") == 1
    assert v.count(v.REJECTED_CASE, "prepare") == 1
    assert v.count(v.APPROVED_CASE, "action") == 1
    assert v.count(v.REJECTED_CASE, "action") == 0
    completed, history = db_count([x[0] for x in created.values()])
    assert completed == 2 and history > 0, (completed, history)
    print(json.dumps({
        "scenario": "A34-two-concurrent-replicas",
        "shared_worker_image": a_image[:18], "two_workers_live_concurrently": True,
        "worker_a": a_id[:12], "worker_b": b_id[:12],
        "worker_b_unchanged_after_worker_a_sigkill": True,
        "native_instance_and_request_identity_preserved": True,
        "mssql_completed": completed, "mssql_history_rows": history,
        "prepare_replayed": 0, "approved_actions": 1, "rejected_actions": 0,
        "status": "PASS-LOCAL-ONE-DOCKER-HOST"
    }, ensure_ascii=False))


def container_id(name: str) -> str:
    return run("docker", "inspect", "-f", "{{.Id}}", name)


if __name__ == "__main__":
    main()
