"""G6 platform-owned non-idempotent HTTP tool dispatch/receipt facts.

Trust boundary: call observe() only with a receipt retrieved by a trusted Tool
Adapter from an authoritative external read-only receipt API. This POC does not
authenticate enterprise MCP, guarantee side-effect exactly-once, or retry.
Absence of a receipt is never evidence of no side effect.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

import psycopg
from psycopg.rows import dict_row

from task_ledger import TaskFactConflict, _id


_DIGEST = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ToolDispatchIntent:
    run_id: str
    attempt_id: str
    execution_id: str
    adapter_id: str
    operation_id: str
    request_sha256: str


@dataclass(frozen=True)
class ExternalToolReceipt:
    execution_id: str
    adapter_id: str
    operation_id: str
    external_receipt_id: str
    result_sha256: str
    result_kind: str = "COMMITTED"


class ToolReceiptReconciler:
    def __init__(self, dsn: str):
        if not dsn:
            raise ValueError("Platform PostgreSQL DSN required")
        self.dsn = dsn

    def prepare(self, intent: ToolDispatchIntent) -> None:
        """One irreversible dispatch admission. Must commit before HTTP POST.

        A duplicate prepare never authorizes a second side-effect invocation.
        """
        if not all(vars(intent).values()) or not _DIGEST.fullmatch(intent.request_sha256):
            raise ValueError("Complete frozen dispatch identity and SHA256 required")
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT state FROM poc_runs WHERE run_id=%s FOR UPDATE",
                            (intent.run_id,))
                run = cur.fetchone()
                if not run or run["state"] != "RUNNING":
                    raise TaskFactConflict("Tool dispatch Run is not active")
                cur.execute(
                    """SELECT a.state AS attempt_state,e.state AS execution_state,
                              e.side_effect_class,p.run_id
                       FROM poc_executions e
                       JOIN poc_attempts a ON a.attempt_id=e.attempt_id
                       JOIN poc_steps s ON s.step_id=a.step_id
                       JOIN poc_plans p ON p.plan_id=s.plan_id
                       WHERE e.execution_id=%s AND a.attempt_id=%s FOR UPDATE OF a,e""",
                    (intent.execution_id, intent.attempt_id),
                )
                row = cur.fetchone()
                if not row or row["run_id"] != intent.run_id:
                    raise TaskFactConflict("Tool dispatch execution lineage mismatch")
                if row["attempt_state"] != "RUNNING" or row["execution_state"] != "RUNNING":
                    raise TaskFactConflict("Cannot dispatch a non-running execution")
                if row["side_effect_class"] in ("PURE", "IDEMPOTENT"):
                    raise TaskFactConflict("Non-idempotent receipt protocol requires a risky execution")
                try:
                    cur.execute(
                        """INSERT INTO poc_tool_dispatch_intents
                           (execution_id,run_id,attempt_id,adapter_id,operation_id,request_sha256)
                           VALUES (%s,%s,%s,%s,%s,%s)""",
                        (intent.execution_id, intent.run_id, intent.attempt_id,
                         intent.adapter_id, intent.operation_id, intent.request_sha256),
                    )
                except psycopg.errors.UniqueViolation as exc:
                    raise TaskFactConflict("Tool dispatch already prepared: never call side effect again") from exc

    def inspect(self, execution_id: str) -> str:
        """Read-only; it never grants permission to dispatch."""
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            row = conn.execute(
                """SELECT i.execution_id,r.execution_id AS receipt_execution,
                          rc.state AS reconciliation_state
                   FROM poc_tool_dispatch_intents i
                   LEFT JOIN poc_side_effect_receipts r ON r.execution_id=i.execution_id
                   LEFT JOIN poc_reconciliations rc ON rc.execution_id=i.execution_id
                   WHERE i.execution_id=%s""",
                (execution_id,),
            ).fetchone()
        if row is None:
            return "NO_DISPATCH_INTENT"
        if row["receipt_execution"] is not None:
            return "RECEIPT_RECORDED"
        if row["reconciliation_state"] is not None:
            return "UNKNOWN_NEEDS_EXTERNAL_RECEIPT"
        return "DISPATCH_OUTCOME_UNCERTAIN"

    def observe(self, run_id: str, receipt: ExternalToolReceipt | None, *,
                execution_id: str) -> str:
        """Persist authoritative receipt after UNKNOWN; never call the tool.

        A missing authoritative receipt is inconclusive and leaves PENDING.
        Caller must independently authenticate/validate the Tool Adapter.
        """
        if receipt is None:
            return "RECEIPT_NOT_FOUND_REMAINS_UNKNOWN"
        if not all(vars(receipt).values()) or not _DIGEST.fullmatch(receipt.result_sha256):
            raise ValueError("Complete external receipt identity and SHA256 required")
        if receipt.result_kind != "COMMITTED" or receipt.execution_id != execution_id:
            raise TaskFactConflict("External receipt identity/outcome mismatch")
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT state FROM poc_runs WHERE run_id=%s FOR UPDATE", (run_id,))
                run = cur.fetchone()
                if run is None:
                    raise TaskFactConflict("Unknown Run")
                cur.execute(
                    """SELECT i.run_id,i.attempt_id,i.adapter_id,i.operation_id,
                              e.side_effect_class,e.state AS execution_state,
                              a.state AS attempt_state,
                              rc.state AS reconciliation_state,
                              sr.external_receipt_id,sr.result_sha256,sr.result_kind
                       FROM poc_tool_dispatch_intents i
                       JOIN poc_executions e ON e.execution_id=i.execution_id
                       JOIN poc_attempts a ON a.attempt_id=i.attempt_id
                       LEFT JOIN poc_reconciliations rc ON rc.execution_id=i.execution_id
                       LEFT JOIN poc_side_effect_receipts sr ON sr.execution_id=i.execution_id
                       WHERE i.execution_id=%s FOR UPDATE OF e,a""",
                    (execution_id,),
                )
                row = cur.fetchone()
                if row is None or row["run_id"] != run_id:
                    raise TaskFactConflict("Receipt Run/Execution lineage mismatch")
                if receipt.adapter_id != row["adapter_id"] or receipt.operation_id != row["operation_id"]:
                    raise TaskFactConflict("External operation or adapter identity mismatch")
                if row["external_receipt_id"] is not None:
                    if (row["external_receipt_id"] == receipt.external_receipt_id
                        and row["result_sha256"] == receipt.result_sha256
                        and row["result_kind"] == receipt.result_kind
                        and row["reconciliation_state"] == "RESOLVED"):
                        return "ALREADY_RECONCILED"
                    raise TaskFactConflict("Contradictory external receipt; never overwrite")
                if (run["state"] != "RUNNING"
                    or row["side_effect_class"] in ("PURE", "IDEMPOTENT")
                    or row["execution_state"] != "UNKNOWN"
                    or row["attempt_state"] != "UNKNOWN"
                    or row["reconciliation_state"] != "PENDING"):
                    raise TaskFactConflict("Receipt requires UNKNOWN non-idempotent execution and PENDING reconciliation")
                cur.execute(
                    """INSERT INTO poc_side_effect_receipts
                       (execution_id,run_id,adapter_id,operation_id,
                        external_receipt_id,result_sha256,result_kind)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                    (execution_id, run_id, receipt.adapter_id, receipt.operation_id,
                     receipt.external_receipt_id, receipt.result_sha256, receipt.result_kind),
                )
                cur.execute(
                    """UPDATE poc_reconciliations SET state='RESOLVED'
                       WHERE execution_id=%s AND state='PENDING'""",
                    (execution_id,),
                )
                if cur.rowcount != 1:
                    raise TaskFactConflict("Lost pending reconciliation claim")
                seq = cur.execute(
                    "SELECT COALESCE(MAX(seq),0)+1 AS seq FROM poc_events WHERE run_id=%s",
                    (run_id,),
                ).fetchone()["seq"]
                cur.execute(
                    """INSERT INTO poc_events(event_id,run_id,seq,event_type,payload)
                       VALUES (%s,%s,%s,'execution.receipt.confirmed',%s::jsonb)""",
                    (_id("event"),run_id,seq,json.dumps({
                        "execution_id": execution_id,
                        "receipt_id": receipt.external_receipt_id,
                        "result_kind": receipt.result_kind,
                    })),
                )
        # Reconciliation completed but original Attempt remains UNKNOWN:
        # a separate decision is required to close/run the task safely.
        return "RECEIPT_CONFIRMED_NO_REDISPATCH"
