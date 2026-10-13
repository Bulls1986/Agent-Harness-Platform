"""DEV-M5 REAL physical Hatchet Worker A -> B with the SAME Cube MicroVM.

Three authoritative boundaries are deliberately distinct:
- Hatchet embedded Engine on its own PostgreSQL owns technical retry.
- Harness PostgreSQL owns frozen Run/Scope/Workspace/Lease/Epoch/Binding.
- Cube owns one actual MicroVM and its Guest files.

After Worker A creates the REAL Cube and writes the Guest proof, the
controller SIGKILLs the entire OS group. A new Worker B receives Hatchet's
native retry, acquires PG fencing epoch 8, connects to the ORIGINAL Cube ID,
reads identical bytes, and releases the Cube. Never redispatch Cube.create.

This is a single-host synthetic test, NOT production cross-host isolation.
"""
from __future__ import annotations

from datetime import timedelta
import json
import os
import signal
import subprocess
import sys
import threading
import tempfile
import time
import traceback
from uuid import uuid4

from hatchet_sdk import ClientConfig, Context, EmbeddedHatchetConfig, Hatchet
from pydantic import BaseModel
from poc.closed_loop.facts import PgFacts, UnsafeDispatch
from poc.sandbox.cube_binding import CubeBinding, CubeWorkspaceGateway, NativeCubeTransport

ROLE = os.environ.get("HARNESS_M5_FLEET_ROLE", "controller")
hatchet = Hatchet.from_embedded(ClientConfig(
    embedded=EmbeddedHatchetConfig(
        database_url=os.environ["HATCHET_POC_DATABASE_URL"],
        run_migrations=(ROLE == "controller"),
    ),
))


class CubeInput(BaseModel):
    run_id: str
    execution_id: str
    scope: str
    workspace_ref: str
    environment_digest: str


workflow = hatchet.workflow(
    name="harness-m5-physical-worker-cube-preserve-v1",
    input_validator=CubeInput,
)


def proof_path(input: CubeInput) -> str:
    return "/workspace/" + input.execution_id + ".txt"


def proof_bytes(input: CubeInput) -> str:
    return "synthetic-guest-proof:" + input.execution_id


@workflow.task(retries=2, backoff_factor=1,
               execution_timeout=timedelta(seconds=48))
def cube_task(input: CubeInput, ctx: Context) -> dict:
    db = PgFacts()
    for _ in range(180):
        try:
            binding = CubeBinding(db).get(input.execution_id)
            with db.tx() as c:
                native = c.execute(
                    "SELECT state,provider_workflow_id FROM harness_run WHERE id=%s",
                    (input.run_id,),
                ).fetchone()
            if native == ("RUNNING", ctx.workflow_run_id):
                break
        except KeyError:
            pass  # Control plane is still committing original Run/Binding.
        time.sleep(.1)
    else:
        raise UnsafeDispatch("No immutable Harness Run and Cube binding")

    gateway = CubeWorkspaceGateway(CubeBinding(db), NativeCubeTransport())
    if ROLE == "worker-A":
        if ctx.retry_count != 0 or binding.state != "ALLOCATING":
            raise UnsafeDispatch("Only fresh Worker A may create Cube")
        original_id = gateway.allocate(input.execution_id, "worker-A", 7)
        gateway.write(input.execution_id, "worker-A", 7,
                      proof_path(input), proof_bytes(input))
        if gateway.read(input.execution_id, "worker-A", 7,
                        proof_path(input)) != proof_bytes(input):
            raise RuntimeError("Worker A did not durably write Guest proof")
        print("CUBE_WORKER_A_GUEST_FILE_READY " + original_id, flush=True)
        # Controller waits for the persistent binding + actual Guest bytes
        # and force-kills the entire Worker A OS process group.
        while True:
            time.sleep(1)

    if ROLE != "worker-B" or ctx.retry_count < 1:
        raise UnsafeDispatch("Expected independent B on native Hatchet retry")

    binding_authority = CubeBinding(db)
    # Technical scheduling is Hatchet's. A short bounded wait is only for
    # PostgreSQL server-clock expiration of A's existing execution lease,
    # never a retry of the non-idempotent Cube create operation.
    deadline = time.monotonic() + 35
    while True:
        try:
            current = binding_authority.takeover(
                input.execution_id, expected_epoch=7,
                new_owner="worker-B", scope=input.scope,
                workspace=input.workspace_ref,
                environment_digest=input.environment_digest,
                lease_seconds=110,
            )
            break
        except UnsafeDispatch:
            if time.monotonic() > deadline:
                raise
            time.sleep(.4)
    if current.fencing_epoch != 8 or not current.sandbox_id:
        raise UnsafeDispatch("B cannot recover without original native Cube ID")
    try:
        gateway.read(input.execution_id, "worker-A", 7, proof_path(input))
    except UnsafeDispatch:
        pass
    else:
        raise UnsafeDispatch("Fenced old Worker A still accesses Cube")
    recovered = CubeWorkspaceGateway(CubeBinding(PgFacts()), NativeCubeTransport())
    bytes_read = recovered.read(input.execution_id, "worker-B", 8, proof_path(input))
    if bytes_read != proof_bytes(input):
        raise RuntimeError("B lost original Guest workspace data")
    # Native SDK Guest Shell/Git is fenced by the same current PG owner.
    git=recovered.command(input.execution_id,"worker-B",8,"git --version")
    if git.exit_code!=0 or "git version" not in git.stdout:
        raise RuntimeError("Worker B did not execute Git inside original Cube Guest")
    recovered.release(input.execution_id, "worker-B", 8)
    if CubeBinding(db).get(input.execution_id).state != "RELEASED":
        raise RuntimeError("Native Cube release was not confirmed in PG")
    return {
        "status": "PASS_PHYSICAL_HATCHET_CUBE_WORKSPACE_TAKEOVER",
        "worker_role": ROLE,
        "worker_pid": os.getpid(),
        "native_retry_count": ctx.retry_count,
        "provider_workflow_run_id": ctx.workflow_run_id,
        "sandbox_id": current.sandbox_id,
        "workspace_ref": current.workspace,
        "fencing_epoch": current.fencing_epoch,
        "original_guest_bytes": True,
        "native_destroy_and_pg_release": True,
        "native_guest_git": True,
        "host_shell_fallback": False,
    }


def launch(role: str, diagnostics: dict[str, str]) -> subprocess.Popen:
    env = dict(os.environ, HARNESS_M5_FLEET_ROLE=role)
    # Synthetic-only test logs are printed on failure; never leak runtime
    # environment/secrets, and never suppress Worker startup exceptions.
    path = os.path.join(tempfile.gettempdir(),
                        "harness-m5-" + role + "-" + uuid4().hex + ".log")
    diagnostics[role] = path
    with open(path, "w", encoding="utf-8") as log:
        return subprocess.Popen(
            [sys.executable, "-B", "-m",
             "poc.sandbox.verify_hatchet_cube_worker_takeover", "worker"],
            env=env, stdin=subprocess.DEVNULL,
            stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True,
        )


def wait_for_a(binding: CubeBinding, execution: str, a: subprocess.Popen,
               content: str, path: str) -> str:
    until = time.monotonic() + 100
    while time.monotonic() < until:
        if a.poll() is not None:
            raise RuntimeError("Worker A terminated before controlled SIGKILL")
        fact = binding.get(execution)
        if fact.state == "ACTIVE" and fact.sandbox_id:
            # Independent Native SDK observation, not trusting PG ACTIVE
            # alone to prove A already persisted the actual Guest file.
            try:
                sb = NativeCubeTransport().connect(fact.sandbox_id)
                if sb.files.read(path) == content:
                    return fact.sandbox_id
            except Exception:
                pass
        time.sleep(.35)
    fact = binding.get(execution)
    raise RuntimeError("Worker A never persisted expected native Guest proof: "
                       + f"binding_state={fact.state} native_id={fact.sandbox_id}")


def verify() -> dict:
    for name in ("CUBE_API_URL", "CUBE_TEMPLATE_ID",
                 "HARNESS_POC_DATABASE_URL", "HATCHET_POC_DATABASE_URL"):
        if not os.environ.get(name):
            raise RuntimeError("Real runtime must configure " + name)
    db = PgFacts()
    binding = CubeBinding(db)
    run_id = "m5-cube-hatchet-" + uuid4().hex
    execution = "cube-" + run_id
    scope = "synthetic-scope-" + run_id
    workspace = "synthetic-workspace-" + run_id
    digest = "sha256:synthetic-frozen-image"
    command = db.create(run_id, prompt="synthetic Cube physical Worker failover")
    db.dispatch(command)
    diagnostics: dict[str, str] = {}
    a = launch("worker-A", diagnostics)
    b = None
    sid = None
    success = False
    try:
        time.sleep(6)
        if a.poll() is not None:
            raise RuntimeError("Worker A could not start")
        ref = workflow.run(
            CubeInput(run_id=run_id, execution_id=execution, scope=scope,
                      workspace_ref=workspace, environment_digest=digest),
            wait_for_result=False,
        )
        db.bind(command, ref.workflow_run_id)
        binding.begin(
            execution_id=execution, run_id=run_id, scope=scope,
            workspace=workspace, environment_digest=digest,
            owner_id="worker-A", fencing_epoch=7, lease_seconds=36,
        )
        input = CubeInput(run_id=run_id, execution_id=execution, scope=scope,
                          workspace_ref=workspace, environment_digest=digest)
        sid = wait_for_a(binding, execution, a, proof_bytes(input), proof_path(input))
        os.killpg(a.pid, signal.SIGKILL)
        a.wait(timeout=12)
        if a.returncode != -signal.SIGKILL:
            raise RuntimeError("A physical OS process was not SIGKILLed")
        print("PHYSICAL_CUBE_WORKER_A_SIGKILL", a.pid, sid, flush=True)
        b = launch("worker-B", diagnostics)
        out = hatchet.runs.get_run_ref(ref.workflow_run_id).result()
        if not isinstance(out, dict) or len(out) != 1:
            raise RuntimeError("No true native Hatchet task result")
        proof = next(iter(out.values()))
        if (not isinstance(proof, dict)
                or proof.get("status") != "PASS_PHYSICAL_HATCHET_CUBE_WORKSPACE_TAKEOVER"
                or proof.get("worker_role") != "worker-B"
                or proof.get("worker_pid") != b.pid
                or proof.get("native_retry_count", 0) < 1
                or proof.get("provider_workflow_run_id") != ref.workflow_run_id
                or proof.get("sandbox_id") != sid
                or proof.get("fencing_epoch") != 8
                or proof.get("original_guest_bytes") is not True):
            raise RuntimeError("Hatchet/PG/real Cube identity mismatch " + repr(out))
        snapshot = db.snapshot(run_id)
        events = snapshot["events"]
        for name in ("sandbox.binding.creation_dispatched",
                     "sandbox.binding.confirmed",
                     "sandbox.binding.transferred",
                     "sandbox.binding.released"):
            if sum(e["type"] == name for e in events) != 1:
                raise RuntimeError("Missing/duplicate persisted " + name)
        if binding.get(execution).state != "RELEASED":
            raise RuntimeError("Real Cube was not released")
        success = True
        return {
            "outcome": "PASS_REAL_PHYSICAL_HATCHET_CUBE_PG_TAKEOVER",
            "run_id": run_id,
            "hatchet_workflow_run_id": ref.workflow_run_id,
            "cube_sandbox_id": sid,
            "worker_a_pid": a.pid, "worker_a_exit": a.returncode,
            "worker_b_pid": b.pid,
            "retry_count": proof["native_retry_count"],
            "pg_fencing_epoch": 8,
            "guest_original_content_kept": True,
            "native_guest_git": proof.get("native_guest_git") is True,
            "host_shell_fallback": False,
            "cube_release_confirmed": True,
            "cross_host": "NOT_TESTED",
            "guest_inflight_fencing": "NOT_TESTED",
        }
    finally:
        for proc in (a, b):
            if proc is not None and proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait(timeout=8)
        if not success:
            for role, path in diagnostics.items():
                try:
                    with open(path, encoding="utf-8", errors="replace") as log:
                        tail = log.readlines()[-100:]
                    print("SYNTHETIC_" + role + "_STARTUP_DIAGNOSTIC_BEGIN", flush=True)
                    print("".join(tail)[-9000:], flush=True)
                    print("SYNTHETIC_" + role + "_STARTUP_DIAGNOSTIC_END", flush=True)
                except OSError:
                    print("SYNTHETIC_" + role + "_DIAGNOSTIC_UNAVAILABLE", flush=True)
        for path in diagnostics.values():
            try:
                os.remove(path)
            except OSError:
                pass
        if not success and sid:
            # ONLY emergency cleanup for an isolated synthetic test.
            # Do not use this Host privileged path from the Harness runtime.
            print("SYNTHETIC_TEST_FAILED_RECONCILE_NATIVE_SANDBOX", sid, flush=True)
            try:
                NativeCubeTransport().connect(sid).kill()
                print("OUT_OF_BAND_SYNTHETIC_SANDBOX_CLEANUP", flush=True)
            except Exception:
                print("NATIVE_CUBE_CLEANUP_UNKNOWN_MANUAL_FOLLOWUP", flush=True)


def main() -> None:
    if len(sys.argv) == 2 and sys.argv[1] == "worker":
        hatchet.worker("harness-m5-real-cube-" + ROLE,
                      workflows=[workflow]).start()
        return
    if len(sys.argv) != 2 or sys.argv[1] != "controller":
        raise ValueError("controller or worker")
    result = 0
    try:
        print(json.dumps(verify(), sort_keys=True), flush=True)
    except Exception:
        result = 1
        traceback.print_exc()
    finally:
        hatchet.stop_embedded()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(result)


if __name__ == "__main__":
    main()
