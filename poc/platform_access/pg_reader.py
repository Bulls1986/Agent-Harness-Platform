"""Real PostgreSQL read projection for the DEV-M7 scoped Run contract.

The trusted Run creation path persists ownership facts to Harness PG. This
adapter never derives access from a request header, Provider ID or local
Inspector payload. Legacy unscoped Runs are intentionally invisible to the
authorized facade. Authentication/policy decisions are external injections.
"""
from __future__ import annotations

from poc.closed_loop.facts import PgFacts
from poc.platform_access.authorized_reads import RunBinding


class PgRunReader:
    """Read-only adapter backed by authoritative Harness Run facts."""

    def __init__(self, facts: PgFacts):
        if not isinstance(facts, PgFacts):
            raise ValueError("A real Harness PostgreSQL facts adapter is required")
        self._facts = facts

    def binding(self, run_id: str) -> RunBinding:
        with self._facts.tx() as c:
            row = c.execute(
                "SELECT id,project_scope,initiator_principal_id "
                "FROM harness_run WHERE id=%s", (run_id,),
            ).fetchone()
        if not row or not all(isinstance(v, str) and v.strip() for v in row):
            # An unscoped historical POC Run is NOT authorizable.
            raise KeyError(run_id)
        return RunBinding(
            run_id=row[0],
            project_scope=row[1],
            initiator_principal_id=row[2],
        )

    def snapshot(self, run_id: str) -> dict:
        return self._facts.snapshot(run_id)

    def events_since(self, run_id: str, after: int, limit: int) -> list[dict]:
        return self._facts.events_since(run_id, after, limit)
