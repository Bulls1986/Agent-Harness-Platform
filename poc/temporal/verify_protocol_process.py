"""C10 actual HTTP-process restart against the C06/C07 live fault Run.

No Temporal Client used in this bridge; all state and SSE events come from the
persisted Harness PostgreSQL after real non-idempotent crash/quarantine.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request


def _get(base: str, path: str, *, last_id: str | None = None):
    req=urllib.request.Request(
        base+path,headers={"Last-Event-ID":last_id} if last_id else {})
    with urllib.request.urlopen(req,timeout=8) as resp:
        raw=resp.read().decode()
        ctype=resp.headers.get("Content-Type","")
        return json.loads(raw) if "application/json" in ctype else raw


def _start(port: int) -> subprocess.Popen:
    proc=subprocess.Popen(
        [sys.executable,"-m","uvicorn","protocol_bridge:app",
         "--app-dir","poc/temporal","--host","127.0.0.1","--port",str(port),
         "--no-access-log","--log-level","error"],
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        env=os.environ.copy())
    base=f"http://127.0.0.1:{port}"
    for _ in range(95):
        if proc.poll() is not None:
            raise AssertionError("Harness HTTP adapter subprocess terminated")
        try:
            if _get(base,"/health")["status"]=="ready":
                return proc
        except (OSError,ValueError):
            time.sleep(.12)
    proc.kill()
    raise TimeoutError("Harness HTTP adapter not ready")


def _stop(proc: subprocess.Popen | None) -> None:
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def assert_process_restart(run_id: str, native_workflow_id: str) -> dict:
    if not os.environ.get("POC_C_PLATFORM_DSN"):
        raise AssertionError("Harness PostgreSQL DSN required")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        port=sock.getsockname()[1]
    base=f"http://127.0.0.1:{port}"
    first=second=None
    try:
        first=_start(port)
        response=_get(base,f"/v1/responses/{run_id}")
        stream=_get(base,f"/v1/runs/{run_id}/events")
        if (response["status"]!="in_progress" or
                response["harness"]["attention_required"] is not True or
                response["harness"]["execution_outcome"]!="UNKNOWN" or
                response["harness"]["reconciliation_status"]!="PENDING"):
            raise AssertionError("C10 falsely classified Native activity completion as Harness success")
        if stream.count("event: ")!=2 or "event: execution.unknown" not in stream:
            raise AssertionError("C10 persisted event stream mismatch")
        if native_workflow_id in json.dumps(response) or native_workflow_id in stream:
            raise AssertionError("Private native Workflow identifier leaked to UI")
        _stop(first);first=None
        second=_start(port)
        response2=_get(base,f"/v1/responses/{run_id}")
        replay=_get(base,f"/v1/runs/{run_id}/events",last_id=run_id+":1")
        if response2!=response or replay.count("event: ")!=1:
            raise AssertionError("C10 HTTP process restart lost PG state/cursor")
        if "id: "+run_id+":2" not in replay or "event: execution.unknown" not in replay:
            raise AssertionError("C10 reconnect cursor failed")
        return {
            "status":"PASS_C10_RESTRICTED_HTTP_AFTER_REAL_TEMPORAL_CRASH",
            "new_http_process_recovered_same_run":True,
            "typed_events":2,
            "last_event_id_replayed":True,
            "native_workflow_id_hidden":True,
            "harness_status":"in_progress",
            "reconciliation_status":"PENDING",
            "full_responses_api_proven":False,
            "model_token_sse_proven":False,
        }
    finally:
        _stop(first)
        _stop(second)


if __name__=="__main__":
    if len(sys.argv)!=3:
        raise SystemExit("Usage: verify_protocol_process.py <platform-run-id> <native-workflow-id>")
    print(json.dumps(assert_process_restart(sys.argv[1],sys.argv[2]),sort_keys=True))
