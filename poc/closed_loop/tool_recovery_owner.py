"""Limited HC-03 PostgreSQL execution owner/fencing for HC-02 reconciliation.

NOT a replacement for Hatchet task dispatch, Cube sandbox leases or runtime
policy. This grants authority to reconcile an already UNKNOWN non-idempotent
Tool, NEVER authority to replay the external side effect. Clock and CAS are
PostgreSQL-server based, not request-input or workflow payload authority.
"""
from __future__ import annotations

from dataclasses import dataclass

from poc.closed_loop.facts import PgFacts, UnsafeDispatch
from poc.closed_loop.tool_receipt import ToolReceiptJournal


@dataclass(frozen=True)
class RecoveryPermit:
    execution_id: str
    owner_id: str
    fencing_epoch: int


class ToolRecoveryOwner:
    def __init__(self, facts: PgFacts):
        if not isinstance(facts,PgFacts):
            raise ValueError("Trusted PostgreSQL Harness authority required")
        self.facts=facts
        self.journal=ToolReceiptJournal(facts)
        with self.facts.tx() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS harness_tool_recovery_authority (
                    execution_id TEXT PRIMARY KEY
                        REFERENCES harness_tool_intent(execution_id),
                    owner_id TEXT NOT NULL,
                    fencing_epoch BIGINT NOT NULL CHECK (fencing_epoch>=1),
                    lease_expires_at TIMESTAMPTZ NOT NULL,
                    revision BIGINT NOT NULL DEFAULT 1
                )
            """)

    @staticmethod
    def _validate_owner(owner_id: str, epoch: int, lease_seconds: int = 30):
        if (not isinstance(owner_id,str) or not owner_id
                or owner_id != owner_id.strip()
                or type(epoch) is not int or epoch < 1
                or type(lease_seconds) is not int
                or not 1 <= lease_seconds <= 3600):
            raise ValueError("Invalid trusted execution owner/epoch/lease")

    def initialize(self, execution_id: str, owner_id: str,
                   epoch: int, *, lease_seconds: int = 30) -> RecoveryPermit:
        self._validate_owner(owner_id,epoch,lease_seconds)
        fact=self.journal.inspect(execution_id)
        with self.facts.tx() as c:
            run=c.execute(
                "SELECT state,plan_version,provider_workflow_id "
                "FROM harness_run WHERE id=%s FOR UPDATE",
                (fact["run_id"],),
            ).fetchone()
            intent=c.execute(
                "SELECT owner_id,fencing_epoch,state FROM harness_tool_intent "
                "WHERE execution_id=%s FOR UPDATE",(execution_id,),
            ).fetchone()
            if (not run or run[0]!="RUNNING" or not run[2]
                    or run[1]!=fact["plan_version"]
                    or not intent or intent[0]!=owner_id or intent[1]!=epoch
                    or intent[2] not in ("RECORDED","DISPATCHED","UNKNOWN")):
                raise UnsafeDispatch("No trusted frozen Tool execution for owner")
            if c.execute(
                "SELECT 1 FROM harness_tool_recovery_authority WHERE execution_id=%s",
                (execution_id,),
            ).fetchone():
                raise UnsafeDispatch("Cannot reinitialize existing recovery authority")
            c.execute(
                "INSERT INTO harness_tool_recovery_authority("
                "execution_id,owner_id,fencing_epoch,lease_expires_at) "
                "VALUES (%s,%s,%s,now()+(%s * interval '1 second'))",
                (execution_id,owner_id,epoch,lease_seconds),
            )
        return RecoveryPermit(execution_id,owner_id,epoch)

    def admit(self, execution_id: str, owner_id: str,
              epoch: int) -> RecoveryPermit:
        self._validate_owner(owner_id,epoch)
        with self.facts.tx() as c:
            row=c.execute(
                "SELECT owner_id,fencing_epoch,lease_expires_at>now() "
                "FROM harness_tool_recovery_authority WHERE execution_id=%s",
                (execution_id,),
            ).fetchone()
            if row!=(owner_id,epoch,True):
                raise UnsafeDispatch("STALE_EXECUTION_OWNER / LEASE_EXPIRED")
        return RecoveryPermit(execution_id,owner_id,epoch)

    def takeover(self, execution_id: str, new_owner: str, *,
                 expected_epoch: int, lease_seconds: int = 30) -> RecoveryPermit:
        self._validate_owner(new_owner,expected_epoch,lease_seconds)
        fact=self.journal.inspect(execution_id)
        with self.facts.tx() as c:
            # Lock Run, then Tool Intent, then owner authority: same order as
            # the Receipt finalize transaction. A concurrent late old owner
            # cannot submit a stale Receipt after this CAS commits.
            run=c.execute(
                "SELECT state,plan_version,provider_workflow_id "
                "FROM harness_run WHERE id=%s FOR UPDATE",
                (fact["run_id"],),
            ).fetchone()
            intent=c.execute(
                "SELECT state,plan_version FROM harness_tool_intent "
                "WHERE execution_id=%s FOR UPDATE",(execution_id,),
            ).fetchone()
            row=c.execute(
                "SELECT owner_id,fencing_epoch,lease_expires_at<=now() "
                "FROM harness_tool_recovery_authority "
                "WHERE execution_id=%s FOR UPDATE",(execution_id,),
            ).fetchone()
            if (not run or run[0]!="RUNNING" or not run[2]
                    or run[1]!=fact["plan_version"]
                    or intent!=("UNKNOWN",fact["plan_version"])
                    or not row or row[1]!=expected_epoch or not row[2]
                    or row[0]==new_owner):
                raise UnsafeDispatch(
                    "Recovery takeover needs expired epoch and UNKNOWN effect")
            new_epoch=expected_epoch+1
            c.execute(
                "UPDATE harness_tool_recovery_authority SET "
                "owner_id=%s,fencing_epoch=%s,"
                "lease_expires_at=now()+(%s * interval '1 second'),"
                "revision=revision+1 WHERE execution_id=%s",
                (new_owner,new_epoch,lease_seconds,execution_id),
            )
            PgFacts.event(c,fact["run_id"],"tool.recovery.owner.transferred",{
                "execution_id":execution_id,
                "from_owner":row[0],"to_owner":new_owner,
                "old_epoch":expected_epoch,"new_epoch":new_epoch,
                "tool_replayed":False,
            })
        return RecoveryPermit(execution_id,new_owner,new_epoch)

    def reconcile(self, execution_id: str, owner_id: str, epoch: int,
                  trusted_lookup) -> str:
        # Read gate is an early rejection. The journal repeats it under the
        # same PG transaction as Receipt COMMIT to protect against owner
        # change between slow external query and final Receipt write.
        self.admit(execution_id,owner_id,epoch)
        return self.journal.reconcile(
            execution_id,trusted_lookup,
            recovery_owner=owner_id,recovery_epoch=epoch,
        )
