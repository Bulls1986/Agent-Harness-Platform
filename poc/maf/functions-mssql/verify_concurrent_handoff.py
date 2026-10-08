"""A34: two concurrent identical Functions app replicas share MSSQL TaskHub.

Worker A is the sole worker when Prepare/approval waiting begins; Worker B
joins the SAME TaskHub while A is alive. SIGKILL A; B completes native HITL.
Only the separate maf-mssql-a34 project containers may be stopped/recreated.
"""
from __future__ import annotations

import json
import os
import re
import sys
import subprocess
import time
from pathlib import Path
import verify_handoff as v

PROJECT = "maf-mssql-a34"
COMPOSE = Path(__file__).resolve().parent.parent / "compose-functions-mssql-a34.yml"
ENVFILE = Path(__file__).resolve().parent / ".env.local"

# Optional PLATFORM fact proof. Without POC_POSTGRES_DSN this remains
# an A33 native HITL worker test, not a claim of platform Same Attempt Resume.
PLATFORM_DSN = os.environ.get("POC_POSTGRES_DSN")
WORKFLOW_VERSION = "maf_mssql_poc_hitl:v1"
RUNTIME_VERSION = "agent-framework-azurefunctions==1.0.0b260922"
WORKFLOW_NAME = "maf_mssql_poc_hitl"
if PLATFORM_DSN:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from approval_wait import ApprovalWaitStore
    from durable_approval_binding import DurableApprovalBindingStore, DurableBindingMismatch
    from durable_approval_delivery import DurableApprovalDelivery
    from task_ledger import TaskLedger
    from workflow_probe import VerificationFact

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
    platform: dict[str, tuple] = {}
    delivery_tokens: dict[str, str] = {}
    if PLATFORM_DSN:
        TaskLedger(PLATFORM_DSN).initialize()
        approval_store = ApprovalWaitStore(PLATFORM_DSN)
        binding_store = DurableApprovalBindingStore(PLATFORM_DSN)
        delivery_store = DurableApprovalDelivery(PLATFORM_DSN)

    for case in cases:
        response = v.invoke("POST", f"{v.ROUTE}/run", case)
        instance = response.get("instanceId")
        assert instance and re.fullmatch("[0-9a-f]{32}", instance), response
        created[case] = instance, v.pending(instance, 95)
        if PLATFORM_DSN:
            fact = VerificationFact.example(passed=False, evidence_ref=None)
            approval = approval_store.request(
                fact, requester_principal="poc-fixture-requester",
                approver_principal="poc-fixture-approver",
                action_ref="tool:poc-simulated-execution",
                resource_ref="resource:poc", policy_ref="policy:poc",
                durable_instance_id=instance,
                durable_request_id=created[case][1],
                durable_workflow_name=WORKFLOW_NAME,
                frozen_workflow_version=WORKFLOW_VERSION,
                frozen_runtime_version=RUNTIME_VERSION,
            )
            platform[case] = (fact, approval)

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
        if PLATFORM_DSN:
            fact, _ = platform[case]
            # Harden freeze before runtime response: simulated incompatible
            # deployment must be rejected, without touching the native wait.
            if case == v.APPROVED_CASE:
                try:
                    binding_store.require_waiting_resume(
                        fact.run_id, attempt_id=fact.attempt_id,
                        native_instance_id=instance,native_request_id=req_id,
                        workflow_name=WORKFLOW_NAME,
                        workflow_version="maf_mssql_poc_hitl:v2-incompatible",
                        runtime_version=RUNTIME_VERSION,
                    )
                except DurableBindingMismatch:
                    pass
                else:
                    raise AssertionError("Version mismatch was not rejected")

    run("docker", "kill", "--signal", "KILL", a_id)
    assert container("worker-b") == b_id
    assert (container_id("maf-mssql-poc-mssql-1"),
            container_id("maf-mssql-poc-azurite-1")) == infra_before
    for case, (instance, request_id) in created.items():
        assert v.pending(instance, 95) == request_id
        if PLATFORM_DSN:
            fact, approval = platform[case]
            binding = binding_store.require_waiting_resume(
                fact.run_id, attempt_id=fact.attempt_id,
                native_instance_id=instance, native_request_id=request_id,
                workflow_name=WORKFLOW_NAME,
                workflow_version=WORKFLOW_VERSION,
                runtime_version=RUNTIME_VERSION,
            )
            assert binding["step_id"] == fact.step_id
            assert len(binding_store.load_attempt_history(fact.run_id)) == 1
            # Trusted local test fixture; NOT a client-supplied IAM authorization.
            approval_store.decide(
                approval.approval_id,
                authenticated_principal="poc-fixture-approver",
                authorized=True,
                decision="APPROVED" if case == v.APPROVED_CASE else "REJECTED",
            )
            # Simulate a process boundary after committed platform Approval
            # but before delivery admission. No native response has been sent.
            claim = DurableApprovalDelivery(PLATFORM_DSN).claim(
                fact.run_id, attempt_id=fact.attempt_id,
                native_instance_id=instance, native_request_id=request_id,
                workflow_name=WORKFLOW_NAME, workflow_version=WORKFLOW_VERSION,
                runtime_version=RUNTIME_VERSION,
            )
            assert claim.state == "CLAIMED" and claim.token
            assert (claim.instance_id, claim.request_id) == (instance, request_id)
            delivery_tokens[case] = claim.token
        v.invoke("POST", f"{v.ROUTE}/respond/{instance}/{request_id}",
                 "APPROVED" if case == v.APPROVED_CASE else "REJECTED")
    for case, (instance, _) in created.items():
        expected = ["SIMULATED_EXECUTION:" + case] if case == v.APPROVED_CASE else ["DENIED_NO_EXECUTION"]
        for _ in range(70):
            status = v.invoke("GET", f"{v.ROUTE}/status/{instance}")
            if status.get("runtimeStatus") == "Completed":
                assert status.get("output") == expected, status
                if PLATFORM_DSN:
                    fact, _ = platform[case]
                    delivery_store.complete(
                        fact.run_id, token=delivery_tokens[case],
                        native_status=status["runtimeStatus"],
                        output_kind=("SIMULATED_EXECUTION" if case == v.APPROVED_CASE
                                     else "DENIED_NO_EXECUTION"),
                    )
                    repeat = delivery_store.claim(
                        fact.run_id, attempt_id=fact.attempt_id,
                        native_instance_id=instance, native_request_id=created[case][1],
                        workflow_name=WORKFLOW_NAME,workflow_version=WORKFLOW_VERSION,
                        runtime_version=RUNTIME_VERSION,
                    )
                    assert repeat.state == "ALREADY_APPLIED" and repeat.token is None
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
    if PLATFORM_DSN:
        for case in cases:
            fact, _ = platform[case]
            attempts = binding_store.load_attempt_history(fact.run_id)
            assert len(attempts) == 1 and attempts[0]["attempt_id"] == fact.attempt_id
    print(json.dumps({
        "platform_approval_attempt_binding": "PASS-WAITING-IDENTITY" if PLATFORM_DSN else "NOT_RUN",
        "platform_inflight_same_attempt_resume": "NOT_PROVEN",
        "workflow_frozen_version_negative_guard": bool(PLATFORM_DSN),
        "committed_decision_before_native_delivery": "PASS" if PLATFORM_DSN else "NOT_RUN",
        "native_response_delivery_token": "APPLIED" if PLATFORM_DSN else "NOT_RUN",
        "post_claim_crash_unknown_guard": "POSTGRES_ONLY" if PLATFORM_DSN else "NOT_RUN",
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
