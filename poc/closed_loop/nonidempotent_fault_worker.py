"""Real subprocess-only fault injector: external ledger commit then SIGKILL.

A disposable process is killed at the precise boundary: after the external
PostgreSQL transaction commits, before returning/persisting the Receipt.
No business consumer, real money/account, network API or secrets involved.
"""
from __future__ import annotations

import argparse
import os
import signal

from poc.closed_loop.facts import PgFacts, UnsafeDispatch
from poc.closed_loop.external_ledger_demo import ExternalLedger
from poc.closed_loop.tool_receipt import ToolReceiptJournal


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--execution-id",required=True)
    parser.add_argument("--phase",choices=("before-commit","after-commit"),required=True)
    args=parser.parse_args()
    db=PgFacts()
    fact=ToolReceiptJournal(db).inspect(args.execution_id)
    with db.tx() as c:
        row=c.execute(
            "SELECT state,plan_version,provider_workflow_id "
            "FROM harness_run WHERE id=%s",(fact["run_id"],),
        ).fetchone()
    if (not row or row[0]!="RUNNING" or not row[2]
            or row[1]!=fact["plan_version"] or fact["state"]!="DISPATCHED"
            or fact["owner_id"]!="worker-A" or fact["fencing_epoch"]!=7):
        raise UnsafeDispatch("Crash worker cannot bypass frozen trusted dispatch")
    ledger=ExternalLedger(os.environ["HARNESS_LEDGER_DATABASE_URL"])
    if args.phase=="before-commit":
        os.kill(os.getpid(),signal.SIGKILL)
    ledger.debit(fact["execution_id"],fact["operation"],
                 fact["target"],fact["idempotency_key"])
    # The separate ledger commit HAS succeeded. The Handler cannot notify
    # Harness, and is force-killed without a finally/exception handler.
    os.kill(os.getpid(),signal.SIGKILL)
    raise AssertionError("SIGKILL did not occur")


if __name__=="__main__":
    main()
