"""DEV-M8 live consumer fixture: genuine API HTTP + Harness PostgreSQL + Hatchet.

The *consumer* lives exclusively in integrations/*.mjs and imports no Harness
modules. This fixture composes platform-owned services with synthetic trust
identities, never customer credentials or private business information.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import json
import os
import socket
import subprocess
import sys
import threading
import time
import traceback

import uvicorn
from poc.closed_loop.facts import PgFacts
from poc.closed_loop.hatchet_pg_live import hatchet, workflow, execute
from poc.closed_loop.real_model import ModelConfiguration
from poc.platform_access.authorized_reads import SecurityContext
from poc.platform_access.pg_reader import PgRunReader
from poc.platform_access.conversation_pg import PgConversationStore
from poc.platform_access.platform_api import create_platform_app


def verify() -> dict:
    if not os.getenv("HARNESS_POC_DATABASE_URL") or not os.getenv("HATCHET_POC_DATABASE_URL"):
        raise RuntimeError("M8 real integration requires independent PostgreSQL database URLs")
    cfg = ModelConfiguration.from_env()
    if cfg.mode != "deterministic_local_model":
        raise RuntimeError("M8 Native CI must not require external LLM secrets")
    primary = SecurityContext("m8-synthetic-user-a", "USER", "m8-synthetic-project-a")
    other = SecurityContext("m8-synthetic-user-b", "USER", "m8-synthetic-project-b")

    def identity(request):
        value = request.headers.get("authorization")
        if value == "Bearer synthetic-m8-primary":
            return primary
        if value == "Bearer synthetic-m8-other":
            return other
        raise ValueError("unauthenticated synthetic request")

    facts = PgFacts()
    store = PgConversationStore(facts)
    executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="m8-native-submit")
    worker = hatchet.worker("harness-m8-synthetic-external-worker", workflows=[workflow])
    worker_thread = threading.Thread(target=worker.start, daemon=True)
    worker_thread.start()
    time.sleep(5)

    def submit(run_id: str, prompt: str, key: str):
        if prompt == "M8 synthetic cancellation in progress":
            # A deliberately held synthetic provider, ONLY for testing the
            # public cancel intent -> PG status boundary. This is NOT proof of
            # native provider termination (which the API explicitly denies).
            facts.dispatch(key)
            facts.bind(key, "m8-synthetic-held-provider-" + run_id)
            return None
        return executor.submit(execute, run_id, prompt, command=key)

    app = create_platform_app(
        resolve_context=identity,
        reader=PgRunReader(PgFacts()), store=store,
        authorize=lambda *_: True,
        authorize_create=lambda *_: True,
        admit_recipe=lambda agent, recipe: (
            agent == "m8-test-agent@v1" and recipe == "m8-test-recipe@v1"
        ),
        start_run=submit,
        model_binding=lambda: (cfg.mode, cfg.model_id),
        cancel_run=PgFacts().request_cancel,
        sse_max_polls=1,
    )

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    server = uvicorn.Server(uvicorn.Config(
        app, host="127.0.0.1", port=port,
        log_level="error", access_log=False,
    ))
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()
    try:
        deadline = time.monotonic() + 12
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.1)
        if not server.started:
            raise RuntimeError("M8 actual API HTTP server failed to start")
        env = dict(os.environ, M8_SYNTHETIC_API_URL=f"http://127.0.0.1:{port}")
        result = subprocess.run(
            ["node", "integrations/verify_m8_http.mjs"],
            env=env, capture_output=True, text=True, timeout=180,
        )
        if result.returncode:
            raise AssertionError(
                "Independent M8 client integration failed:\n"
                + result.stdout[-4000:] + result.stderr[-6000:]
            )
        evidence = json.loads(result.stdout.strip().splitlines()[-1])
        if evidence.get("result") != "PASS":
            raise AssertionError("Live external M8 client did not return PASS")
        return evidence
    finally:
        server.should_exit = True
        server_thread.join(timeout=12)
        executor.shutdown(wait=False, cancel_futures=True)
        hatchet.stop_embedded()


def main() -> None:
    code = 1
    try:
        result = verify()
        print(json.dumps(result, sort_keys=True), flush=True)
        code = 0
    except Exception:
        traceback.print_exc()
    finally:
        # Same bounded native Hatchet embedded-server lifecycle as M7's
        # official verifier: do not leave child gRPC process holding CI.
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)


if __name__ == "__main__":
    main()
