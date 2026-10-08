"""A23 integration: native MAF Document Workflow + PostgreSQL platform facts.

Usage:
  POC_POSTGRES_DSN=postgresql://... python poc/maf/persisted_document.py --case expected
  POC_POSTGRES_DSN=postgresql://... python poc/maf/persisted_document.py --inspect run-...
Does not resume an Agent/Workflow; shows task facts remain readable in a NEW process.
"""
from __future__ import annotations
import argparse
import asyncio
import json
import os
import sys

from document_workflow import run_document_case
from task_ledger import TaskLedger
from workflow_probe import VerificationFact


async def run_case(ledger: TaskLedger, candidate: str) -> dict:
    fact = VerificationFact.example(passed=False, evidence_ref=None)
    execution_id = ledger.start(fact)
    # MAF Workflow executes *outside* the database transaction; task fact
    # finalization is a separate atomic transaction after trusted verification.
    # A crash in between leaves RUNNING and requires explicit recovery policy.
    outcome = await run_document_case(candidate, fact)
    ledger.finish(fact, outcome, execution_id)
    return ledger.read(fact.run_id)


def main() -> int:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--case", choices=("expected", "buggy"))
    action.add_argument("--inspect", metavar="RUN_ID")
    args = parser.parse_args()
    dsn = os.environ.get("POC_POSTGRES_DSN", "")
    if not dsn:
        print("SETUP_ERROR: POC_POSTGRES_DSN is required", file=sys.stderr)
        return 2
    ledger = TaskLedger(dsn)
    try:
        ledger.initialize()
        record = ledger.read(args.inspect) if args.inspect else asyncio.run(
            run_case(ledger, args.case)
        )
    except Exception as exc:
        # Do not print database credentials or raw SQL exceptions to CI logs.
        print(f"RUN_ERROR: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(json.dumps(record, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
