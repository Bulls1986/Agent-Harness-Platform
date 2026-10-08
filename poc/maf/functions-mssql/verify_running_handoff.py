"""Native A34 executing-Executor Worker SIGKILL with official MSSQL TaskHub.

Only the isolated maf-mssql-a34-running workers are stopped/recreated.
Observer markers are not exactly-once guarantees. Never re-submit a /run.
"""
from __future__ import annotations
import json
import os
import sys
import psycopg
import re
import subprocess
import time
from pathlib import Path
import verify_handoff as v
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from recovery_boundary import RecoveryCoordinator
from task_ledger import TaskLedger
from workflow_probe import VerificationFact

PROJECT = "maf-mssql-a34-running"
ROOT = Path(__file__).resolve().parent
COMPOSE = ROOT.parent / "compose-functions-mssql-a34-running.yml"
ENVFILE = ROOT / ".env.local"
A = "http://127.0.0.1:17091"
B = "http://127.0.0.1:17092"
ROUTE = "/api/workflow/maf_mssql_poc_running"


def run(*args: str) -> str:
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT).strip()


def compose(*args: str) -> str:
    return run("docker", "compose", "-p", PROJECT,
               "--env-file", str(ENVFILE), "-f", str(COMPOSE), *args)


def worker(service: str) -> str:
    cid = compose("ps", "-q", service)
    if not re.fullmatch(r"[0-9a-f]{12,64}", cid):
        raise AssertionError(f"Missing {service} container")
    assert run("docker", "inspect", "-f", "{{.State.Running}}", cid) == "true"
    return cid


def native_status(instance: str) -> dict:
    return v.invoke("GET", f"{ROUTE}/status/{instance}")


def query_history(instance: str) -> tuple[str, int]:
    if not re.fullmatch(r"[0-9a-f]{32}", instance):
        raise ValueError("Invalid native instance ID")
    q = ("SET NOCOUNT ON; SELECT RuntimeStatus FROM dt.Instances "
         f"WHERE InstanceID='{instance}'; SELECT COUNT(*) FROM dt.History "
         f"WHERE InstanceID='{instance}';")
    cmd = ('/opt/mssql-tools18/bin/sqlcmd -C -b -h -1 -W '
           '-S localhost -U sa -P "$MSSQL_SA_PASSWORD" '
           f'-d DurableA34Running -Q "{q}"')
    out = run("docker", "exec", "maf-mssql-poc-mssql-1", "/bin/bash", "-lc", cmd)
    rows = [x.strip() for x in out.splitlines() if x.strip()]
    if len(rows) != 2 or not rows[1].isdigit():
        raise AssertionError(f"Unexpected MSSQL audit: {out[:250]!r}")
    return rows[0], int(rows[1])


def main() -> None:
    if not ENVFILE.exists():
        raise RuntimeError("Missing ignored local SQL env fixture")
    dsn = os.environ.get("POC_POSTGRES_DSN")
    ledger = fact = execution_id = None
    if dsn:
        ledger = TaskLedger(dsn)
        ledger.initialize()
        fact = VerificationFact.example(passed=False, evidence_ref=None)
        execution_id = ledger.start(fact, initiator="poc-running-crash-fixture")
        with psycopg.connect(dsn) as conn:
            conn.execute("UPDATE poc_executions SET side_effect_class='NON_RETRYABLE' "
                         "WHERE execution_id=%s", (execution_id,))
    case = "running-fixture-" + v._NONCE
    v.BASE = A
    assert v.count(case, "prepare") == v.count(case, "dispatch_observed") == 0
    compose("stop", "worker-b")
    compose("up", "-d", "--force-recreate", "--no-deps", "worker-a")
    a = worker("worker-a")
    v.wait_for_host(150)
    resp = v.invoke("POST", f"{ROUTE}/run", case)
    instance = resp.get("instanceId")
    if not instance or not re.fullmatch(r"[0-9a-f]{32}", instance):
        raise AssertionError(f"Native instance missing: {resp!r}")
    end = time.monotonic() + 95
    while time.monotonic() < end and not v.count(case, "dispatch_observed"):
        time.sleep(0.4)
    assert v.count(case, "prepare") == 1
    assert v.count(case, "dispatch_observed") == 1, "Handler never became RUNNING"
    assert v.count(case, "completed_observed") == 0
    before = native_status(instance)
    assert before.get("runtimeStatus") not in ("Completed", "Failed", "Terminated"), before
    # A remains alive when B connects to the same official TaskHub.
    compose("up", "-d", "--force-recreate", "--no-deps", "worker-b")
    b = worker("worker-b")
    assert a != b
    v.BASE = B
    v.wait_for_host(150)
    assert worker("worker-a") == a and worker("worker-b") == b
    assert run("docker", "inspect", "-f", "{{.Image}}", a) == run(
        "docker", "inspect", "-f", "{{.Image}}", b)
    assert v.count(case, "completed_observed") == 0, "Crash window elapsed"
    run("docker", "kill", "--signal", "KILL", a)
    assert worker("worker-b") == b
    # Do not manually enqueue new Workflow or manipulate native MSSQL tables.
    # Real PG platform recovery fact: non-PURE dispatch was interrupted.
    # This is a task-level safety decision, not a claim that the native
    # Durable Engine will honor a platform STOP in its own replay path.
    if dsn:
        decision = RecoveryCoordinator(dsn).recover(
            fact.run_id, interrupted_attempt_id=fact.attempt_id)
        assert decision.outcome == "RECONCILIATION", decision
        read = ledger.read(fact.run_id)
        assert len(read["attempts"]) == 1
        assert read["attempts"][0]["state"] == "UNKNOWN"
        assert RecoveryCoordinator(dsn).recover(
            fact.run_id, interrupted_attempt_id=fact.attempt_id).outcome == "NO_UNIQUE_ACTIVE_EXECUTION"
    state = None
    for _ in range(165):
        state = native_status(instance)
        status = state.get("runtimeStatus")
        if status == "Completed":
            assert state.get("output") == ["SIMULATED_RUNNING:" + case], state
            break
        if status in ("Failed", "Terminated"):
            raise AssertionError(f"Interrupted Executor failed: {state!r}")
        time.sleep(2)
    else:
        raise TimeoutError(f"Native running Workflow did not complete: {state!r}")
    prepare = v.count(case, "prepare")
    dispatch = v.count(case, "dispatch_observed")
    completed = v.count(case, "completed_observed")
    status, history = query_history(instance)
    assert status == "Completed" and history > 0
    assert prepare == 1, "Completed Prepare Executor was unexpectedly replayed"
    assert dispatch >= 1 and completed >= 1
    # A native Completed signal does NOT retroactively certify the platform
    # NON_RETRYABLE Execution or authorize a second external tool dispatch.
    if dsn:
        final = ledger.read(fact.run_id)
        assert len(final["attempts"]) == 1
        assert final["attempts"][0]["attempt_id"] == fact.attempt_id
        assert final["attempts"][0]["state"] == "UNKNOWN"
        with psycopg.connect(dsn) as conn:
            recon = conn.execute(
                "SELECT state FROM poc_reconciliations WHERE execution_id=%s",
                (execution_id,),
            ).fetchone()
        assert recon and recon[0] == "PENDING"
    print(json.dumps({
        "scenario": "A34-native-RUNNING-Executor-SIGKILL",
        "native_nonterminal_during_handler": True,
        "worker_a_killed": a[:12],
        "worker_b_remained_online": b[:12],
        "native_instance_id": instance,
        "mssql_status": status,
        "mssql_history_rows": history,
        "prepare_executions": prepare,
        "handler_dispatch_observations": dispatch,
        "handler_completions_observed": completed,
        "native_handler_reinvoked": dispatch > 1,
        "platform_run_id": fact.run_id if dsn else None,
        "platform_attempt_id": fact.attempt_id if dsn else None,
        "platform_attempt_count": 1 if dsn else None,
        "platform_execution_state": "UNKNOWN" if dsn else "NOT_RUN",
        "platform_reconciliation_state": "PENDING" if dsn else "NOT_RUN",
        "native_instance_to_platform_immutable_binding": "NOT_PROVEN",
        "platform_running_same_attempt": "NOT_PROVEN",
        "real_external_side_effect_exactly_once": "NOT_PROVEN",
        "nonpure_unknown_policy": "REQUIRES_RECONCILIATION",
        "status": "PASS_NATIVE_RUNNING_CRASH_OBSERVATION",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
