"""Start one real Hatchet Engine/Worker and local-only Run Inspector."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
import logging
import os
import threading

import uvicorn
from fastapi import FastAPI
from .facts import PgFacts
from .inspector import create_app

LOG = logging.getLogger(__name__)


def launch_server() -> FastAPI:
    # The module imports public Hatchet SDK only when the REAL server starts.
    # Inspector API contract tests can run without the optional Agent SDKs.
    from .hatchet_pg_live import hatchet, workflow, execute

    pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="workflow-submission")
    worker = hatchet.worker("harness-inspector-shared-worker", workflows=[workflow])
    started = threading.Event()
    error: list[str] = []

    def serve_worker():
        started.set()
        try:
            worker.start()
        except Exception as exc:
            error.append(type(exc).__name__)
            LOG.exception("Real Hatchet worker stopped unexpectedly")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            PgFacts()  # No startup without actual PostgreSQL.
            threading.Thread(target=serve_worker, daemon=True,
                             name="real-hatchet-worker").start()
            if not started.wait(timeout=10) or error:
                raise RuntimeError("Real Hatchet Worker is unavailable")
            yield
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
            hatchet.stop_embedded()

    def submit(run_id: str, prompt: str, key: str):
        if error:
            raise RuntimeError("Real Hatchet Worker failed")
        def background():
            try:
                execute(run_id, prompt, command=key)
            except Exception as exc:
                if PgFacts().run_state(run_id) == 'CANCELLED':
                    LOG.info('Run %s cancelled by operator; no execution error',run_id)
                    return
                LOG.exception("Run %s could not be confirmed", run_id)
                try:
                    PgFacts().report_execution_error(run_id, type(exc).__name__)
                except Exception:
                    LOG.exception("Could not persist failed execution observation")
        return pool.submit(background)

    # No privileged worker access from the legacy Inspector by default.
    # Operator must explicitly opt into the fixed real B03 runner, provide
    # a distinct long credential, and run in an authorized Linux environment.
    trusted_runner = None
    if os.getenv("HARNESS_INSPECTOR_NATIVE_B03_ENABLED") == "1":
        from .trusted_scenario_runner import TrustedScenarioRunner
        key = os.environ.get("HARNESS_INSPECTOR_SCENARIO_TOKEN", "")
        storage = os.environ.get("HARNESS_INSPECTOR_EVIDENCE_DIR", "")
        if not storage or len(key) < 32:
            raise RuntimeError("Native B03 opt-in requires token and evidence directory")
        trusted_runner = TrustedScenarioRunner(token=key, evidence_dir=storage)
    app = create_app(submit=submit, trusted_runner=trusted_runner)
    app.router.lifespan_context = lifespan
    return app


def main():
    logging.basicConfig(level=logging.INFO)
    # Container port uses 0.0.0.0 internally; docker compose restricts HOST
    # publishing to 127.0.0.1. Host direct usage binds only to loopback.
    uvicorn.run(launch_server(),
                host=os.getenv("HARNESS_INSPECTOR_HOST", "127.0.0.1"),
                port=int(os.getenv("HARNESS_INSPECTOR_PORT", "8765")))


if __name__ == "__main__":
    main()
