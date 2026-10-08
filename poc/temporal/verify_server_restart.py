"""C04 native Temporal dev-server restart with persisted SQLite mid HITL.

This is a separate OS/container crash boundary from Worker SIGKILL.
Preserves Temporal history using a Docker named volume. Dev-server
persistence is not a production HA/backend certification.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time
from datetime import timedelta
from uuid import uuid4

from temporalio.client import Client

from verify_local_handoff import ADDRESS, start_worker, stop_worker, wait_phase
from workflow import DocumentReviewWorkflow

CONTAINER = os.environ.get("POC_C_TEMPORAL_CONTAINER", "poc-c-temporal-dev")
PG_CONTAINER = os.environ.get("POC_C_TEMPORAL_POSTGRES_CONTAINER")


def docker(*args: str) -> str:
    return subprocess.check_output(["docker", *args], text=True, stderr=subprocess.STDOUT).strip()


def pg_history_nodes() -> int | None:
    if not PG_CONTAINER:
        return None
    output=docker("exec",PG_CONTAINER,"psql","-U","temporal","-d","temporal",
                  "-X","-qAt","-c","SELECT count(*) FROM history_node;")
    return int(output)


async def connect_retry(seconds: float = 35) -> Client:
    until = time.monotonic() + seconds
    last = None
    while time.monotonic() < until:
        try:
            return await Client.connect(ADDRESS)
        except Exception as exc:
            last = type(exc).__name__
            await asyncio.sleep(0.45)
    raise RuntimeError(f"Temporal unavailable after server restart: {last}")


async def main() -> None:
    queue = "poc-c-restart-" + uuid4().hex[:12]
    run_id = "run-" + uuid4().hex
    workflow_id = "temporal-poc-c-" + uuid4().hex
    attempts = ["attempt-" + uuid4().hex, "attempt-" + uuid4().hex]
    worker_a = worker_b = None
    restarted = False
    try:
        if docker("inspect", "-f", "{{.State.Running}}", CONTAINER) != "true":
            raise RuntimeError("Isolated Temporal container not running")
        if PG_CONTAINER:
            image=docker("inspect","-f","{{.Config.Image}}",CONTAINER)
            if not image.startswith("temporalio/server:"):
                raise AssertionError("PG backend check requires non-dev OSS Temporal server")
        client = await connect_retry()
        worker_a = start_worker(queue)
        handle = await client.start_workflow(
            DocumentReviewWorkflow.run,
            {"run_id": run_id, "attempt_ids": attempts},
            id=workflow_id, task_queue=queue,
            execution_timeout=timedelta(minutes=4),
        )
        snap = await wait_phase(handle, "WAITING_APPROVAL", timeout=30)
        if snap["attempts"][0]["verification"] != "FAILED":
            raise AssertionError("Expected failed verification before approval")
        stop_worker(worker_a)
        worker_a = None

        # Actually stop the Temporal SERVER process, not just client/worker.
        pg_before = pg_history_nodes()

        docker("stop", "-t", "5", CONTAINER)
        if docker("inspect", "-f", "{{.State.Running}}", CONTAINER) != "false":
            raise AssertionError("Temporal Server did not actually stop")
        pg_during = pg_history_nodes()
        if PG_CONTAINER and (pg_during is None or pg_before is None or pg_during < pg_before or pg_during < 1):
            raise AssertionError("PostgreSQL native history missing with server stopped")
        docker("start", CONTAINER)
        restarted = True
        fresh = await connect_retry()
        recovered = fresh.get_workflow_handle(workflow_id)
        worker_b = start_worker(queue)
        await wait_phase(recovered, "WAITING_APPROVAL", timeout=35)
        await recovered.signal(DocumentReviewWorkflow.decide, "APPROVED")
        result = await asyncio.wait_for(recovered.result(), timeout=35)
        if result["run_id"] != run_id or result["state"] != "COMPLETED":
            raise AssertionError("Native Instance was lost across server restart")
        if result["plan_version"] != 2 or [
            a["attempt_id"] for a in result["attempts"]] != attempts:
            raise AssertionError("Plan/Attempt lineage was lost across restart")
        history = [evt async for evt in recovered.fetch_history_events()]
        complete = sum(1 for e in history if e.HasField("activity_task_completed_event_attributes"))
        if complete != 4:
            raise AssertionError(f"Expected 4 durable completed activities, got {complete}")
        print(json.dumps({
            "status": ("PASS_NATIVE_SERVER_RESTART_OSS_POSTGRES" if PG_CONTAINER
                       else "PASS_NATIVE_SERVER_RESTART_PERSISTED_SQLITE"),
            "worker_a_force_killed": True,
            "server_container_stopped_started": True,
            "workflow_continues_same_native_id": True,
            "platform_run_id_distinct": workflow_id != run_id,
            "activity_completions": complete,
            "history_events": len(history),
            "plan_versions": [1, 2],
            "same_platform_attempts_after_restart": True,
            "storage_backend": ("oss_postgresql_named_volume" if PG_CONTAINER
                                else "dev_server_sqlite_named_volume"),
            "pg_history_nodes_before_stop": pg_before,
            "pg_history_nodes_while_server_offline": pg_during,
            "pg_history_nodes_after": pg_history_nodes(),
            "production_backend_or_HA_proven": False,
        }, sort_keys=True), flush=True)
    finally:
        stop_worker(worker_a)
        stop_worker(worker_b)
        # Leave isolated service running for reproducible next tests.
        try:
            if docker("inspect", "-f", "{{.State.Running}}", CONTAINER) != "true":
                docker("start", CONTAINER)
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
