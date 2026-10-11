"""Synthetic external NON-IDEMPOTENT ledger on a different PostgreSQL DB.

There is intentionally NO uniqueness constraint on idempotency_key or
execution_id in this external system. Calling debit twice makes TWO rows.
This is a fault-injection device, not a business ledger or Harness schema.
"""
from __future__ import annotations

import psycopg

from poc.closed_loop.tool_receipt import EffectEvidence


class ExternalLedger:
    def __init__(self,url:str):
        if not url:
            raise ValueError("An independent ledger PostgreSQL URL is required")
        self.url=url
        with psycopg.connect(self.url) as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS synthetic_external_effect (
                    id BIGSERIAL PRIMARY KEY,
                    execution_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    target TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)

    def debit(self,execution_id:str,operation:str,target:str,idempotency_key:str) -> str:
        # A real irreversible commit; intentionally no server-side dedup.
        with psycopg.connect(self.url) as c:
            row=c.execute(
                "INSERT INTO synthetic_external_effect "
                "(execution_id,operation,target,idempotency_key) "
                "VALUES (%s,%s,%s,%s) RETURNING id",
                (execution_id,operation,target,idempotency_key),
            ).fetchone()
        return "synthetic-ledger:"+str(row[0])

    def find(self,execution_id:str) -> list[EffectEvidence]:
        with psycopg.connect(self.url) as c:
            rows=c.execute(
                "SELECT id,execution_id,operation,target,idempotency_key "
                "FROM synthetic_external_effect WHERE execution_id=%s ORDER BY id",
                (execution_id,),
            ).fetchall()
        return [EffectEvidence("synthetic-ledger:"+str(i),e,op,target,key)
                for i,e,op,target,key in rows]
