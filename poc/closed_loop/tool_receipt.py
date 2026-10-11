"""DEV-M4 limited HC-02 durable non-idempotent Tool Intent/Receipt journal.

This is an isolated, synthetic integration gate, NOT a runtime Tool API,
general Approval/Fencing service or generic exactly-once execution engine.
The trusted worker must be admitted by HC-03 before calling dispatch.
UNKNOWN is never automatically retried; reconciliation is evidence-only.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable, Sequence

from poc.closed_loop.facts import PgFacts, UnsafeDispatch


@dataclass(frozen=True)
class EffectEvidence:
    external_reference: str
    execution_id: str
    operation: str
    target: str
    idempotency_key: str


class ToolReceiptJournal:
    _columns = ("run_id", "plan_version", "step_id", "attempt_id",
                "execution_id", "owner_id", "fencing_epoch", "operation",
                "target", "idempotency_key", "state", "external_reference")

    def __init__(self, facts: PgFacts):
        if not isinstance(facts, PgFacts):
            raise ValueError("Harness PostgreSQL authority is required")
        self.facts = facts
        self.init_schema()

    def init_schema(self):
        with self.facts.tx() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS harness_tool_intent (
                    execution_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES harness_run(id),
                    plan_version INTEGER NOT NULL CHECK (plan_version >= 1),
                    step_id TEXT NOT NULL,
                    attempt_id TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    fencing_epoch BIGINT NOT NULL CHECK (fencing_epoch >= 1),
                    operation TEXT NOT NULL,
                    target TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    side_effect_class TEXT NOT NULL DEFAULT 'NON_RETRYABLE'
                        CHECK (side_effect_class = 'NON_RETRYABLE'),
                    state TEXT NOT NULL CHECK (state IN
                        ('RECORDED','DISPATCHED','UNKNOWN','CONFIRMED_SUCCESS')),
                    external_reference TEXT UNIQUE,
                    failure_reason TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)

    def _read(self, c, execution_id, *, lock=False):
        query = ("SELECT " + ",".join(self._columns) +
                 " FROM harness_tool_intent WHERE execution_id=%s" +
                 (" FOR UPDATE" if lock else ""))
        row = c.execute(query, (execution_id,)).fetchone()
        return dict(zip(self._columns, row)) if row else None

    def inspect(self, execution_id: str) -> dict:
        with self.facts.tx() as c:
            r = self._read(c, execution_id)
        if r is None:
            raise KeyError(execution_id)
        return r

    @staticmethod
    def _replan_pending(c, run_id: str, plan_version: int) -> bool:
        if not c.execute(
            "SELECT to_regclass('harness_replan_intent') IS NOT NULL",
        ).fetchone()[0]:
            return False
        return bool(c.execute(
            "SELECT 1 FROM harness_replan_intent "
            "WHERE run_id=%s AND from_version=%s",
            (run_id, plan_version),
        ).fetchone())

    def register_intent(
        self, run_id: str, plan_version: int, step_id: str, attempt_id: str,
        execution_id: str, owner_id: str, fencing_epoch: int,
        operation: str, target: str, idempotency_key: str,
    ) -> str:
        parts=(run_id,step_id,attempt_id,execution_id,owner_id,
               operation,target,idempotency_key)
        if (not all(isinstance(x,str) and x.strip()==x and x for x in parts)
                or type(plan_version) is not int or plan_version < 1
                or type(fencing_epoch) is not int or fencing_epoch < 1):
            raise ValueError("Frozen Tool execution and owner fields required")
        expected=(run_id,plan_version,step_id,attempt_id,execution_id,
                  owner_id,fencing_epoch,operation,target,idempotency_key)
        with self.facts.tx() as c:
            run = c.execute(
                "SELECT state,plan_version,provider_workflow_id FROM harness_run "
                "WHERE id=%s FOR UPDATE",(run_id,),
            ).fetchone()
            if not run or run[0]!="RUNNING" or run[1]!=plan_version or not run[2]:
                raise UnsafeDispatch("Unbound/stale Run cannot register Tool Intent")
            if self._replan_pending(c,run_id,plan_version):
                raise UnsafeDispatch("Frozen Replan blocks new non-PURE Tool Intent")
            current = self._read(c, execution_id, lock=True)
            if current:
                present = tuple(current[k] for k in self._columns[:10])
                if present != expected:
                    raise UnsafeDispatch("Conflicting Tool execution identity")
                return execution_id
            # Cross-execution key reuse would make recovery ambiguous.
            if c.execute("SELECT 1 FROM harness_tool_intent WHERE idempotency_key=%s",
                         (idempotency_key,)).fetchone():
                raise UnsafeDispatch("Intent key already owned by another execution")
            c.execute(
                "INSERT INTO harness_tool_intent("
                + ",".join(self._columns[:10]) + ",state) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'RECORDED')",
                expected,
            )
            PgFacts.event(c,run_id,"tool.intent.recorded",
                          {"execution_id":execution_id,"plan_version":plan_version})
        return execution_id

    def dispatch(self, execution_id: str, owner_id: str, fencing_epoch: int):
        with self.facts.tx() as c:
            # Lock Run first, then the Intent: same lock order for every
            # writer, including a concurrent Replan and recovery path.
            info=self._read(c,execution_id)
            if not info:
                raise UnsafeDispatch("Unknown Tool execution")
            run=c.execute(
                "SELECT state,plan_version,provider_workflow_id FROM harness_run "
                "WHERE id=%s FOR UPDATE",(info["run_id"],),
            ).fetchone()
            item=self._read(c,execution_id,lock=True)
            if (run is None or run[0]!="RUNNING" or not run[2]
                    or run[1]!=item["plan_version"]
                    or item["state"]!="RECORDED"
                    or item["owner_id"]!=owner_id
                    or item["fencing_epoch"]!=fencing_epoch
                    or self._replan_pending(c,item["run_id"],item["plan_version"])):
                raise UnsafeDispatch("Duplicate/stale/Replanned Tool; never redispatch")
            c.execute(
                "UPDATE harness_tool_intent SET state='DISPATCHED' WHERE execution_id=%s",
                (execution_id,),
            )
            PgFacts.event(c,item["run_id"],"tool.dispatched",
                          {"execution_id":execution_id})
        return "DISPATCHED"

    def mark_unknown(self, execution_id: str, reason: str) -> str:
        if reason not in ("EXECUTOR_CRASH","LOST_ACK","TIMEOUT_AFTER_DISPATCH"):
            raise ValueError("Only a known failure class may mark Tool UNKNOWN")
        with self.facts.tx() as c:
            info=self._read(c,execution_id)
            if not info:
                raise UnsafeDispatch("Unknown Tool execution")
            c.execute("SELECT id FROM harness_run WHERE id=%s FOR UPDATE",
                      (info["run_id"],))
            item=self._read(c,execution_id,lock=True)
            if item["state"]=="UNKNOWN":
                return "UNKNOWN"
            if item["state"]!="DISPATCHED":
                raise UnsafeDispatch("Only dispatched Tool may become UNKNOWN")
            c.execute(
                "UPDATE harness_tool_intent SET state='UNKNOWN',failure_reason=%s "
                "WHERE execution_id=%s",(reason,execution_id),
            )
            PgFacts.event(c,item["run_id"],"tool.outcome.unknown",
                          {"execution_id":execution_id,"failure_type":reason})
        return "UNKNOWN"

    def require_confirmed(self, execution_id: str) -> str:
        fact=self.inspect(execution_id)
        if fact["state"]!="CONFIRMED_SUCCESS" or not fact["external_reference"]:
            raise UnsafeDispatch("Receipt not confirmed: block downstream side effects")
        return fact["external_reference"]

    def reconcile(
        self, execution_id: str,
        trusted_lookup: Callable[[str],Sequence[EffectEvidence]],
    ) -> str:
        """A trusted external ledger query provides correlation proof; no redo.

        No match is NOT a proof of non-execution (eventual consistency/crash).
        Two effects are not an acceptable receipt even if both share a key.
        """
        original=self.inspect(execution_id)
        if original["state"]=="CONFIRMED_SUCCESS":
            return "CONFIRMED_SUCCESS"
        if original["state"] not in ("UNKNOWN","DISPATCHED"):
            raise UnsafeDispatch("Tool not dispatched; no external result to reconcile")
        try:
            rows=trusted_lookup(execution_id)
        except Exception:
            raise UnsafeDispatch("External receipt query unavailable; keep UNKNOWN") from None
        if (not isinstance(rows,(tuple,list)) or len(rows)!=1
                or not isinstance(rows[0],EffectEvidence)):
            raise UnsafeDispatch("Absent or ambiguous external effect; keep UNKNOWN")
        evidence=rows[0]
        if (not evidence.external_reference
                or evidence.execution_id != original["execution_id"]
                or evidence.operation != original["operation"]
                or evidence.target != original["target"]
                or evidence.idempotency_key != original["idempotency_key"]):
            raise UnsafeDispatch("External Receipt does not match frozen Intent")

        with self.facts.tx() as c:
            c.execute("SELECT id FROM harness_run WHERE id=%s FOR UPDATE",
                      (original["run_id"],))
            item=self._read(c,execution_id,lock=True)
            if item["state"]=="CONFIRMED_SUCCESS":
                if item["external_reference"]!=evidence.external_reference:
                    raise UnsafeDispatch("Conflicting confirmed external receipt")
                return "CONFIRMED_SUCCESS"
            if (item["state"] not in ("DISPATCHED","UNKNOWN")
                    or any(item[k]!=original[k] for k in self._columns[:10])):
                raise UnsafeDispatch("Tool intent changed while reconciling")
            c.execute(
                "UPDATE harness_tool_intent SET state='CONFIRMED_SUCCESS',"
                "external_reference=%s WHERE execution_id=%s",
                (evidence.external_reference,execution_id),
            )
            PgFacts.event(c,item["run_id"],"tool.receipt.confirmed",
                          {"execution_id":execution_id,
                           "external_reference":evidence.external_reference,
                           "source":"external_ledger_query",
                           "replayed_execution":False})
        return "CONFIRMED_SUCCESS"
