"""A26: crash-aware delivery of an already persisted platform Approval.

The Approval decision is immutable in PostgreSQL. The native Runtime response
is NOT in that transaction. We can recover the pre-delivery crash gap safely;
after the delivery intent starts, an unacknowledged result is UNKNOWN and
must not be replayed without reconciliation. No exactly-once claim.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row


class DeliveryConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class DeliveryClaim:
    state: str
    token: str | None
    decision: str
    request_id: str
    checkpoint_ref: str
    workflow_name: str
    output_kind: str | None = None


class ApprovalDelivery:
    def __init__(self, dsn: str):
        if not dsn:
            raise ValueError("PostgreSQL DSN required")
        self.dsn = dsn

    def load_decided(self, run_id: str) -> dict:
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            row = conn.execute(
                """SELECT a.approval_id,a.run_id,a.state AS decision,
                          b.native_request_id,b.native_checkpoint_ref,b.native_workflow_name,
                          r.state AS run_state
                   FROM poc_approvals a
                   JOIN poc_maf_approval_bindings b ON b.approval_id=a.approval_id
                   JOIN poc_runs r ON r.run_id=a.run_id
                   WHERE a.run_id=%s AND a.state IN ('APPROVED','REJECTED')""",
                (run_id,),
            ).fetchone()
            if row is None:
                raise KeyError("No persisted native approval decision for this Run")
            expected = "RUNNING" if row["decision"] == "APPROVED" else "FAILED"
            if row["run_state"] != expected:
                raise DeliveryConflict("Persisted Approval and Run disagree")
            return dict(row)

    def claim(self, run_id: str) -> DeliveryClaim:
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                # Serialize competing responders through the authoritative Run.
                cur.execute("SELECT state FROM poc_runs WHERE run_id=%s FOR UPDATE", (run_id,))
                run = cur.fetchone()
                if run is None:
                    raise KeyError(run_id)
                cur.execute(
                    """SELECT a.approval_id,a.state AS decision,b.native_request_id,
                              b.native_checkpoint_ref,b.native_workflow_name
                       FROM poc_approvals a
                       JOIN poc_maf_approval_bindings b ON b.approval_id=a.approval_id
                       WHERE a.run_id=%s AND a.state IN ('APPROVED','REJECTED')""",
                    (run_id,),
                )
                a = cur.fetchone()
                if a is None:
                    raise DeliveryConflict("No committed decision; cannot resume Runtime")
                expected = "RUNNING" if a["decision"] == "APPROVED" else "FAILED"
                if run["state"] != expected:
                    raise DeliveryConflict("Run/Approval state mismatch")
                cur.execute(
                    """SELECT delivery_token,state,output_kind
                       FROM poc_maf_hitl_deliveries WHERE approval_id=%s FOR UPDATE""",
                    (a["approval_id"],),
                )
                row = cur.fetchone()
                if row is None:
                    token = f"delivery-{uuid4().hex}"
                    cur.execute(
                        """INSERT INTO poc_maf_hitl_deliveries
                           (approval_id,delivery_token,state)
                           VALUES (%s,%s,'IN_FLIGHT')""",
                        (a["approval_id"],token),
                    )
                    state, output = "CLAIMED", None
                elif row["state"] == "APPLIED":
                    token, state, output = None, "ALREADY_APPLIED", row["output_kind"]
                else:
                    # The previous Runtime response may have dispatched effects.
                    # Even if it actually crashed before dispatch, do not assume.
                    if row["state"] == "IN_FLIGHT":
                        cur.execute(
                            """UPDATE poc_maf_hitl_deliveries SET state='UNKNOWN'
                               WHERE approval_id=%s""",
                            (a["approval_id"],),
                        )
                    token, state, output = None, "UNKNOWN_REQUIRES_RECONCILIATION", None
                return DeliveryClaim(
                    state=state, token=token, decision=a["decision"],
                    request_id=a["native_request_id"],
                    checkpoint_ref=a["native_checkpoint_ref"],
                    workflow_name=a["native_workflow_name"],
                    output_kind=output,
                )

    def complete(self, run_id: str, *, token: str, output_kind: str) -> None:
        if not token:
            raise DeliveryConflict("Delivery fencing token required")
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT state FROM poc_runs WHERE run_id=%s FOR UPDATE", (run_id,))
                if cur.fetchone() is None:
                    raise KeyError(run_id)
                cur.execute(
                    """SELECT a.state AS decision,d.state AS delivery_state,
                              d.delivery_token
                       FROM poc_maf_hitl_deliveries d
                       JOIN poc_approvals a ON a.approval_id=d.approval_id
                       WHERE a.run_id=%s FOR UPDATE OF d""",
                    (run_id,),
                )
                row = cur.fetchone()
                if row is None or row["delivery_state"] != "IN_FLIGHT" or row["delivery_token"] != token:
                    raise DeliveryConflict("Stale or uncertain delivery cannot commit")
                expected = "SIMULATED_EXECUTION" if row["decision"] == "APPROVED" else "DENIED_NO_EXECUTION"
                if output_kind != expected:
                    raise DeliveryConflict("Native output conflicts with persisted Approval")
                cur.execute(
                    """UPDATE poc_maf_hitl_deliveries
                       SET state='APPLIED',output_kind=%s,completed_at=now()
                       WHERE delivery_token=%s""",
                    (output_kind,token),
                )
