"""DEV-M5-B03: real Hatchet OS Worker A SIGKILL -> B + same real Cube Guest.

Unlike the separate M4 physical-worker and M5 Cube SDK smokes, this uses
ONE Harness Run/Execution/Native Workflow. No fake Cube, test-only Host file
fallback, or retry of unknown non-idempotent side effects. This is a
Linux-only explicit LIVE acceptance probe, not a production Agent gateway.
"""
from __future__ import annotations

from datetime import timedelta
import json
import os
import signal
import subprocess
import sys
import time
import traceback
from uuid import uuid4
from pydantic import BaseModel

from poc.closed_loop.facts import PgFacts, UnsafeDispatch
from poc.sandbox.cube_binding import CubeBinding, CubeWorkspaceGateway, NativeCubeTransport
from poc.sandbox.joint_gate_contract import validate_joint_evidence


ROLE = os.environ.get("HARNESS_M5_FLEET_ROLE", "controller")
GUEST_FILE = "/workspace/m5-joint-worker-takeover.txt"


class Input(BaseModel):
    run_id: str
    execution_id: str


def require_live_environment():
    required = (
        "CUBE_API_URL", "CUBE_TEMPLATE_ID",
        "HARNESS_POC_DATABASE_URL", "HATCHET_POC_DATABASE_URL",
    )
    absent = [key for key in required if not os.environ.get(key)]
    if absent:
        raise RuntimeError("M5_JOINT_LIVE_GATE_NOT_RUN: missing " + ",".join(absent))
    if os.name != "posix" or not hasattr(os, "killpg"):
        raise RuntimeError("M5_JOINT_LIVE_GATE_NOT_RUN: real OS SIGKILL requires Linux")


def build_hatchet():
    from hatchet_sdk import ClientConfig, EmbeddedHatchetConfig, Hatchet
    return Hatchet.from_embedded(ClientConfig(
        embedded=EmbeddedHatchetConfig(
            database_url=os.environ["HATCHET_POC_DATABASE_URL"],
            run_migrations=(ROLE == "controller"),
        ),
    ))


def build_workflow(hatchet):
    from hatchet_sdk import Context

    workflow = hatchet.workflow(
        name="harness-m5-physical-hatchet-cube-workspace-v1",
        input_validator=Input,
    )

    @workflow.task(retries=2, backoff_factor=1,
                   execution_timeout=timedelta(seconds=120))
    def guest_workspace_task(input: Input, ctx: Context) -> dict:
        db = PgFacts()
        binding = CubeBinding(db)
        # The Native SDK is initialized afresh inside the actual Worker process.
        gateway = CubeWorkspaceGateway(binding, NativeCubeTransport())
        for _ in range(150):
            with db.tx() as c:
                run = c.execute(
                    "SELECT state,provider_workflow_id FROM harness_run WHERE id=%s",
                    (input.run_id,),
                ).fetchone()
            try:
                fact = binding.get(input.execution_id)
            except KeyError:
                fact = None
            if (run == ("RUNNING", ctx.workflow_run_id) and fact
                    and fact.run_id == input.run_id):
                break
            time.sleep(0.1)
        else:
            raise UnsafeDispatch("Unbound platform Run/Workflow/Cube Execution")

        original = "synthetic-guest-" + input.run_id
        if ROLE == "worker-A":
            if ctx.retry_count != 0 or fact.state != "ALLOCATING":
                raise UnsafeDispatch("A may create Cube only on original native attempt")
            sid = gateway.allocate(input.execution_id, "worker-A", 7)
            gateway.write(input.execution_id, "worker-A", 7, GUEST_FILE, original)
            if gateway.read(input.execution_id, "worker-A", 7, GUEST_FILE) != original:
                raise UnsafeDispatch("Worker A could not verify real Guest bytes")
            with db.tx() as c:
                PgFacts.event(c, input.run_id, "sandbox.guest.original.confirmed", {
                    "execution_id": input.execution_id,
                    "sandbox_id": sid,
                    "data_type": "synthetic",
                })
            # Controller must kill A's actual process group after the event.
            while True:
                time.sleep(1)

        if ROLE != "worker-B" or ctx.retry_count < 1:
            raise UnsafeDispatch("B must receive an actual Hatchet native retry")
        # The first attempt must have created and bound an actual Sandbox.
        if fact.state != "ACTIVE" or not fact.sandbox_id or fact.fencing_epoch != 7:
            raise UnsafeDispatch("Original Cube Binding is not recoverable")
        old_sid = fact.sandbox_id
        wrong_scope_rejected = False
        try:
            binding.takeover(
                input.execution_id, 7, "worker-B", "wrong-scope",
                fact.workspace, fact.environment_digest,
            )
        except UnsafeDispatch:
            wrong_scope_rejected = True
        if not wrong_scope_rejected:
            raise UnsafeDispatch("Wrong Scope accepted")
        new_fact = binding.takeover(
            input.execution_id, 7, "worker-B",
            fact.scope, fact.workspace, fact.environment_digest, lease_seconds=120,
        )
        if (new_fact.fencing_epoch != 8 or new_fact.sandbox_id != old_sid
                or new_fact.workspace != fact.workspace):
            raise UnsafeDispatch("Wrong PG owner/epoch/original Sandbox identity")
        old_epoch_rejected = False
        try:
            gateway.write(input.execution_id, "worker-A", 7, GUEST_FILE, "stale-A")
        except UnsafeDispatch:
            old_epoch_rejected = True
        if not old_epoch_rejected:
            raise UnsafeDispatch("Stale A mutated Guest after B takeover")
        # New native SDK object and independent PG reader -- NO re-create.
        new_gateway = CubeWorkspaceGateway(CubeBinding(PgFacts()), NativeCubeTransport())
        actual = new_gateway.read(input.execution_id, "worker-B", 8, GUEST_FILE)
        if actual != original:
            raise UnsafeDispatch("Worker B did not see original Guest bytes")
        new_gateway.release(input.execution_id, "worker-B", 8)
        if binding.get(input.execution_id).state != "RELEASED":
            raise UnsafeDispatch("No native Cube Destroy ACK")
        return {
            "run_id": input.run_id,
            "execution_id": input.execution_id,
            "workflow_run_id": ctx.workflow_run_id,
            "b_worker_role": ROLE,
            "native_retry_count": ctx.retry_count,
            "initial_epoch": 7,
            "new_epoch": new_fact.fencing_epoch,
            "a_cube_id": old_sid,
            "b_cube_id": new_fact.sandbox_id,
            "guest_original": original,
            "guest_after_reconnect": actual,
            "old_epoch_rejected": old_epoch_rejected,
            "wrong_scope_rejected": wrong_scope_rejected,
            "destroy_ack": "RELEASED",
        }

    return workflow, Input


def launch_worker(role: str):
    env = dict(os.environ)
    env["HARNESS_M5_FLEET_ROLE"] = role
    return subprocess.Popen(
        [sys.executable, "-B", "-m",
         "poc.sandbox.verify_hatchet_cube_worker_takeover", "worker"],
        env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def wait_for_original_data(db, binding, run_id, execution_id, worker):
    deadline = time.monotonic() + 330
    while time.monotonic() < deadline:
        if worker.poll() is not None:
            raise RuntimeError("Worker A exited before SIGKILL injection")
        fact = binding.get(execution_id)
        if (fact.state == "ACTIVE" and fact.sandbox_id
                and any(e["type"] == "sandbox.guest.original.confirmed"
                        for e in db.snapshot(run_id)["events"])):
            return fact
        time.sleep(0.5)
    raise RuntimeError("Worker A did not verify real Cube Guest data")


def verify(hatchet, workflow, Input):
    db = PgFacts()
    run_id = "m5-joint-" + uuid4().hex
    execution_id = "cube-exec-" + run_id
    scope = "synthetic-scope-" + run_id
    workspace = "synthetic-workspace-" + run_id
    digest = "sha256:synthetic-frozen-environment"
    command = db.create(run_id, prompt="synthetic same-Run Cube/Worker takeover")
    db.dispatch(command)
    a = launch_worker("worker-A")
    b = None
    binding = CubeBinding(db)
    try:
        time.sleep(6)
        if a.poll() is not None:
            raise RuntimeError("Worker A failed startup")
        ref = workflow.run(Input(run_id=run_id, execution_id=execution_id),
                           wait_for_result=False)
        db.bind(command, ref.workflow_run_id)
        binding.begin(
            execution_id=execution_id, run_id=run_id, scope=scope,
            workspace=workspace, environment_digest=digest,
            owner_id="worker-A", fencing_epoch=7, lease_seconds=600,
        )
        first = wait_for_original_data(db, binding, run_id, execution_id, a)
        os.killpg(a.pid, signal.SIGKILL)
        a.wait(timeout=15)
        if a.returncode != -signal.SIGKILL:
            raise RuntimeError("Actual Worker A OS SIGKILL not observed")
        # Only a controlled *test* lease-expiry injection. Real production
        # handling must wait on trusted PG server-clock and heartbeat rules.
        with db.tx() as c:
            c.execute(
                "UPDATE harness_cube_binding SET lease_expires_at="
                "now()-interval '1 second' WHERE execution_id=%s",
                (execution_id,),
            )
        time.sleep(2.5)
        b = launch_worker("worker-B")
        if b.poll() is not None:
            raise RuntimeError("Independent Worker B failed startup")
        result = hatchet.runs.get_run_ref(ref.workflow_run_id).result()
        if not isinstance(result, dict) or len(result) != 1:
            raise RuntimeError("Hatchet native task proof absent")
        proof = next(iter(result.values()))
        if not isinstance(proof, dict):
            raise RuntimeError("Hatchet B proof malformed")
        evidence = {
            **proof,
            "worker_a_pid": a.pid,
            "worker_a_exit_code": a.returncode,
            "worker_b_pid": b.pid,
        }
        validate_joint_evidence(evidence)
        if (evidence["run_id"] != run_id
                or evidence["execution_id"] != execution_id
                or evidence["workflow_run_id"] != ref.workflow_run_id
                or evidence["a_cube_id"] != first.sandbox_id):
            raise RuntimeError("Joint result not bound to original Run/Cube")
        events = db.snapshot(run_id)["events"]
        for name in ("sandbox.binding.requested",
                     "sandbox.binding.confirmed",
                     "sandbox.guest.original.confirmed",
                     "sandbox.binding.transferred",
                     "sandbox.binding.released"):
            if sum(e["type"] == name for e in events) != 1:
                raise RuntimeError("Expected one persisted event: " + name)
        return {
            "outcome": "PASS_PHYSICAL_HATCHET_CUBE_SAME_RUN",
            **{k: v for k, v in evidence.items()
               if k not in ("guest_original", "guest_after_reconnect")},
            "guest_original_bytes_preserved": True,
            "cube_create_count_from_pg": 1,
            "scope_and_old_epoch_denials": True,
            "cross_host": "NOT_TESTED",
            "in_flight_guest_fencing": "NOT_TESTED",
            "production_iam": "NOT_TESTED",
        }
    finally:
        for proc in (a, b):
            if proc is not None and proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
        try:
            fact = binding.get(execution_id)
            if fact.state != "RELEASED":
                print("CUBE_RESOURCE_ACK_UNKNOWN: manual reconciliation required",
                      "run_id=" + run_id, "execution_id=" + execution_id,
                      "state=" + fact.state, flush=True)
        except Exception:
            print("CUBE_BINDING_UNKNOWN: inspect real PG and Cube state", flush=True)


def main():
    require_live_environment()
    hatchet = build_hatchet()
    workflow, Input = build_workflow(hatchet)
    if len(sys.argv) == 2 and sys.argv[1] == "worker":
        hatchet.worker("harness-m5-cube-" + ROLE,
                       workflows=[workflow]).start()
        return
    if sys.argv[1:] != ["controller"]:
        raise ValueError("Use 'controller' or 'worker'")
    code = 0
    try:
        print(json.dumps(verify(hatchet, workflow, Input), sort_keys=True),
              flush=True)
    except Exception:
        code = 1
        traceback.print_exc()
    finally:
        hatchet.stop_embedded()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)


if __name__ == "__main__":
    main()
