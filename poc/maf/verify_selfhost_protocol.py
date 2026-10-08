"""Real separate-process self-host HTTP/restart smoke for POC-A A18/A19/A21.

Launch a disposable loopback-only Uvicorn app, POST the fixed trusted native
MAF document workflow, terminate the HTTP process, launch a NEW process on
the same port, and GET the stable Run + replay SSE from PostgreSQL. Do not
pretend the POC fixture endpoint implements the full Responses API.
"""
from __future__ import annotations
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request


def request(url: str, payload: dict | None = None):
    body=None if payload is None else json.dumps(payload).encode("utf-8")
    req=urllib.request.Request(url,data=body,
          headers={"Content-Type":"application/json"} if body else {},
          method="POST" if body else "GET")
    with urllib.request.urlopen(req,timeout=20) as result:
        data=result.read().decode("utf-8")
        return json.loads(data) if "json" in result.headers.get("Content-Type","") else data


def launch(port: int) -> subprocess.Popen:
    proc=subprocess.Popen(
        [sys.executable,"-m","uvicorn","protocol_service:app",
         "--app-dir","poc/maf","--host","127.0.0.1","--port",str(port),
         "--no-access-log","--log-level","error"],
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        env=os.environ.copy(),
    )
    url=f"http://127.0.0.1:{port}"
    for _ in range(100):
        if proc.poll() is not None:
            raise RuntimeError("POC local HTTP host failed to start")
        try:
            if request(url+"/health")["status"]=="ready":
                return proc
        except (OSError,TimeoutError,ValueError):
            time.sleep(0.10)
    proc.terminate()
    raise TimeoutError("POC HTTP host health timed out")


def stop(proc):
    if proc is not None and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def main():
    if not os.environ.get("POC_POSTGRES_DSN"):
        raise RuntimeError("Dedicated Postgres DSN required")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        port=sock.getsockname()[1]
    base=f"http://127.0.0.1:{port}"
    server=None
    try:
        server=launch(port)
        result=request(base+"/v1/responses",{"input":"document:replan"})
        run=result["id"]
        if result["status"]!="completed" or result["harness"]["event_cursor"]!=4:
            raise AssertionError("Native MAF or real PG Plan/Verify/Replan failed")
        events=request(base+f"/v1/runs/{run}/events?after=1")
        if "event: plan.replanned" not in events:
            raise AssertionError("Typed stream missing persisted replan")
        stop(server)
        server=None
        server=launch(port)
        restored=request(base+f"/v1/responses/{run}")
        reconnect=request(base+f"/v1/runs/{run}/events?after=2")
        if restored!=result:
            raise AssertionError("Different API process did not read same platform Run")
        if reconnect.count("event: ")!=2 or f"id: {run}:4" not in reconnect:
            raise AssertionError("SSE persisted cursor / reconnect mismatch")
        print(json.dumps({
           "status":"PASS_RESTRICTED_SELFHOST_PROTOCOL_RESTART",
           "host":"127.0.0.1",
           "real_maf_workflow":True,
           "pg_run_reloaded_in_new_process":True,
           "plan_versions":2,
           "event_cursor":4,
           "sse_events_after_cursor_2":2,
           "restarted_http_process":True,
           "fixture_only":True,
           "full_responses_compatible":False,
           "live_model_token_sse":False,
        },sort_keys=True))
    finally:
        stop(server)


if __name__=="__main__":
    main()
