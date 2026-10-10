"""True two-process Hatchet Embedded failover POC against one external PostgreSQL.

ONLY pure/retry-safe steps are used. An owner loss is not a green light to
retry an external non-idempotent Tool: Harness still needs UNKNOWN/Reconcile.

Orchestrator starts A, confirms stage 2 executing on A, starts B in parallel,
kills A's *entire process group* (including its sidecar) without restarting it,
then requires Hatchet's B engine/worker to finish and confirm the original Run.
This test never substitutes mocks for Hatchet and fails closed on any timeout.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
from uuid import uuid4


ROLE = os.environ.get("HATCHET_FLEET_ROLE")
if ROLE in {"A", "B"}:
    from hatchet_sdk import ClientConfig, Context, EmbeddedHatchetConfig, Hatchet
    from pydantic import BaseModel

    # Both engine sidecars share one PostgreSQL system database, not separate
    # bundled PGs. B MUST NOT rerun schema migrations.
    hatchet = Hatchet.from_embedded(
        ClientConfig(
            embedded=EmbeddedHatchetConfig(
                database_url=os.environ["HATCHET_FLEET_DATABASE_URL"],
                run_migrations=(ROLE == "A"),
            )
        )
    )

    class PureInput(BaseModel):
        run_id: str

    workflow = hatchet.workflow(
        name="harness-hatchet-external-pg-failover",
        input_validator=PureInput,
    )

    @workflow.task()
    def prepare(input: PureInput, ctx: Context) -> dict[str, str]:
        append_event("prepare", role=ROLE)
        return {"value": "ready"}

    @workflow.task(parents=[prepare], retries=3, execution_timeout=240)
    def complete(input: PureInput, ctx: Context) -> dict[str, str]:
        assert ctx.task_output(prepare)["value"] == "ready"
        append_event("complete.started", role=ROLE)
        if ROLE == "A":
            # Intentionally block the safe step. The parent process kills
            # this OS process group, which includes its embedded sidecar.
            time.sleep(200)
            raise RuntimeError("A must never finish; kill was not injected")
        append_event("complete.finished", role=ROLE)
        return {"result": "recovered-on-B"}


def marker_dir() -> Path:
    return Path(os.environ["HATCHET_FLEET_MARKERS"])


def append_event(kind: str, *, role: str) -> None:
    # Each append is one small O_APPEND write to avoid interleaved records.
    record = json.dumps({"event": kind, "role": role, "time": time.time()}) + "\n"
    path = marker_dir() / "evidence.jsonl"
    fd = os.open(str(path), os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
    try:
        os.write(fd, record.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)


def worker_main() -> None:
    assert ROLE in {"A", "B"}
    worker = hatchet.worker(f"hatchet-fleet-{ROLE}", workflows=[workflow])
    threading.Thread(target=worker.start, daemon=True).start()
    # Worker.start() is async initialization; the original upstream example
    # also waits briefly before submitting a workflow.
    time.sleep(5)
    print(f"worker-{ROLE}-starting", flush=True)
    (marker_dir() / f"{ROLE}.ready").write_text("started", encoding="utf-8")
    if ROLE == "A":
        ref = workflow.run(PureInput(run_id=os.environ["HATCHET_FLEET_RUN_ID"]), wait_for_result=False)
        (marker_dir() / "workflow_id.txt").write_text(ref.workflow_run_id, encoding="utf-8")
        print(f"run_id={ref.workflow_run_id}", flush=True)
    else:
        # Query authoritative workflow terminal result after B observes its
        # own completed step. Do not rely solely on filesystem marker.
        marker = marker_dir() / "workflow_id.txt"
        deadline = time.monotonic() + 220
        while time.monotonic() < deadline:
            if marker.exists() and (marker_dir() / "evidence.jsonl").exists():
                events = read_events()
                if any(e["event"] == "complete.finished" and e["role"] == "B" for e in events):
                    run_id = marker.read_text(encoding="utf-8").strip()
                    result = hatchet.runs.get_run_ref(run_id).result()
                    assert isinstance(result, dict), result
                    (marker_dir() / "B.verified").write_text(
                        json.dumps({"run_id": run_id, "result": result}), encoding="utf-8"
                    )
                    print("authoritative-result-confirmed", flush=True)
                    break
            time.sleep(2)
        else:
            raise TimeoutError("B did not reach a verified terminal result")
    # Keep B Engine alive for the orchestrator to inspect until it kills it.
    while True:
        time.sleep(1)


def read_events():
    path = marker_dir() / "evidence.jsonl"
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def wait_for(what, predicate, seconds: int) -> None:
    stop_at = time.monotonic() + seconds
    while time.monotonic() < stop_at:
        if predicate():
            return
        time.sleep(0.5)
    raise TimeoutError(what)


def terminate_group(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.wait(timeout=12)


def orchestrate() -> None:
    if os.name != "posix":
        raise RuntimeError("failover process-group test requires Linux/POSIX")
    if not os.environ.get("HATCHET_FLEET_DATABASE_URL"):
        raise RuntimeError("HATCHET_FLEET_DATABASE_URL is required: real external PG")
    with tempfile.TemporaryDirectory(prefix="harness-hatchet-fleet-") as temp:
        directory = Path(temp)
        os.environ["HATCHET_FLEET_MARKERS"] = str(directory)
        run_id = f"hatchet-failover-{uuid4().hex}"
        children = []
        logs = {}
        environment = dict(os.environ, HATCHET_FLEET_MARKERS=str(directory),
                           HATCHET_FLEET_RUN_ID=run_id)
        def spawn(role: str):
            out = (directory / f"{role}.log").open("w+", encoding="utf-8")
            logs[role] = out
            proc = subprocess.Popen(
                [sys.executable, "-B", "-m",
                 "poc.durable_engine.hatchet_fleet_failover_live"],
                env={**environment, "HATCHET_FLEET_ROLE": role},
                start_new_session=True,
                stdout=out, stderr=subprocess.STDOUT,
            )
            children.append(proc)
            return proc

        try:
            a = spawn("A")
            wait_for("A worker not started", lambda: (directory / "A.ready").exists() or
                     a.poll() is not None, 75)
            if a.poll() is not None:
                raise RuntimeError(f"A exited before task started: code {a.returncode}")
            wait_for("A did not enter second task", lambda: any(
                e["event"] == "complete.started" and e["role"] == "A"
                for e in read_events()
            ) or a.poll() is not None, 75)
            if a.poll() is not None:
                raise RuntimeError(f"A exited before fault injection: {a.returncode}")
            b = spawn("B")
            wait_for("B worker not started", lambda: (directory / "B.ready").exists() or
                     b.poll() is not None, 75)
            if b.poll() is not None:
                raise RuntimeError(f"B failed to start: {b.returncode}")
            # B engine runs before we kill A, and B is not restarted after.
            terminate_group(a)
            append_event("orchestrator.killed.A", role="orchestrator")
            wait_for("B did not complete and confirm original workflow",
                     lambda: (directory / "B.verified").exists() or b.poll() is not None,
                     190)
            if b.poll() is not None:
                raise RuntimeError(f"B exited before verification: {b.returncode}")
            events = read_events()
            prepare_events = [e for e in events if e["event"] == "prepare"]
            finished = [e for e in events if e["event"] == "complete.finished"]
            asserts = {
                "prepare_once": len(prepare_events) == 1,
                "stage2_A_started": any(e["event"] == "complete.started" and
                                         e["role"] == "A" for e in events),
                "stage2_B_finished_once": len(finished) == 1 and finished[0]["role"] == "B",
                "no_A_reboot": a.poll() is not None,
            }
            assert all(asserts.values()), {"assertions": asserts, "events": events}
            confirmed = json.loads((directory / "B.verified").read_text())
            assert confirmed["run_id"] == (directory / "workflow_id.txt").read_text().strip()
            print(json.dumps({
                "outcome": "PASS", "engine": "hatchet-embedded-0.110.5",
                "storage": "REAL_EXTERNAL_POSTGRESQL",
                "worker_A_not_restarted": True, "worker_B_independent_engine": True,
                "completed_stage_not_reexecuted": True, "failed_inflight_safe_stage_recovered": True,
                "authoritative_run_result": "PASS", "external_side_effect_receipt": "NOT_TESTED",
                "cube": "NOT_TESTED", "token_sse": "NOT_TESTED",
            }, sort_keys=True), flush=True)
        except Exception:
            for log in logs.values():
                log.flush()
            for role in ("A", "B"):
                path = directory / f"{role}.log"
                if path.exists():
                    tail = "\n".join(path.read_text(errors="replace").splitlines()[-55:])
                    print(f"========== {role} LOG TAIL ==========\n{tail}", file=sys.stderr)
            raise
        finally:
            for child in children:
                terminate_group(child)
            for log in logs.values():
                log.close()


if __name__ == "__main__":
    if ROLE in {"A", "B"}:
        worker_main()
    else:
        orchestrate()
