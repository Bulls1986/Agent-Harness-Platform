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

    # LOCAL POC ONLY: explicitly enabled with compose Inspector profile.
    # Synthetic identity is server-owned and cannot be overridden by client
    # request headers. Do not mount on enterprise/production public gateways.
    m7_demo = None
    if os.getenv("HARNESS_INSPECTOR_M7_DEMO_ENABLED") == "1":
        from poc.platform_access.authorized_reads import SecurityContext
        from poc.platform_access.pg_reader import PgRunReader
        from poc.platform_access.conversation_pg import PgConversationStore
        from poc.platform_access.platform_api import create_platform_app
        from .real_model import ModelConfiguration

        principal = SecurityContext("inspector-local-demo", "USER", "inspector-local-demo")
        def admission(agent_ref: str, recipe_ref: str) -> bool:
            return (agent_ref == "dual-sdk-requirements-review@v1"
                    and recipe_ref == "requirements-review@v1")
        def model_binding() -> tuple[str, str | None]:
            cfg = ModelConfiguration.from_env()
            return (cfg.mode, cfg.model_id)

        m7_demo = create_platform_app(
            resolve_context=lambda _request: principal,
            reader=PgRunReader(PgFacts()),
            store=PgConversationStore(PgFacts()),
            # This is a **fixed synthetic LOCAL identity**, not an enterprise
            # IAM/Policy decision. Production adapters are a separate M7 Gate.
            authorize=lambda context, binding, _action: (
                context == principal and binding.project_scope == principal.project_scope
            ),
            authorize_create=lambda context, _action: context == principal,
            admit_recipe=admission,
            start_run=submit,
            model_binding=model_binding,
            cancel_run=PgFacts().request_cancel,
            sse_max_polls=20,
        )

    app = create_app(submit=submit, public_api_app=m7_demo)
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