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
                LOG.exception("Run %s could not be confirmed", run_id)
                try:
                    PgFacts().report_execution_error(run_id, type(exc).__name__)
                except Exception:
                    LOG.exception("Could not persist failed execution observation")
        return pool.submit(background)

    app = create_app(submit=submit)
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