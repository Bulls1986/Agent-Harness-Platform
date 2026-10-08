"""Process-boundary probes for native session storage and safe Step resume.

POC facts are produced by two independent Python processes; this is not
MAF's native checkpoint resume and no real model or external side effect runs.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from agent_framework.openai import OpenAIChatClient
from harness_capabilities import build_harness
from document_workflow import run_document_case
from native_session_store import NativeSessionStore
from recovery_boundary import RecoveryCoordinator
from task_ledger import TaskLedger
from workflow_probe import VerificationFact

FINGERPRINT = "maf-core-1.20.0|openai-compatible|poc-disabled-file-memory-v1"


def create_native_session():
    # Only constructs the MAF Agent, no network call.
    os.environ.setdefault("OPENAI_API_KEY", "ci-no-network-placeholder")
    agent = build_harness(OpenAIChatClient(model="ci-fake-model"))
    return agent.create_session()


def main() -> int:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--create-crashed-run", action="store_true")
    action.add_argument("--resume-pure", metavar="RUN_ID")
    action.add_argument("--mark-unknown", metavar="RUN_ID")
    action.add_argument("--save-session", metavar="RUN_ID")
    action.add_argument("--load-session", metavar="RUN_ID")
    parser.add_argument("--expected-attempt", help="Interrupted Attempt ID to recover (mandatory for recovery)")
    args = parser.parse_args()
    dsn = os.environ.get("POC_POSTGRES_DSN")
    if not dsn:
        print("Missing POC_POSTGRES_DSN", file=sys.stderr)
        return 2
    ledger = TaskLedger(dsn)
    ledger.initialize()
    store = NativeSessionStore(dsn)
    try:
        if args.create_crashed_run:
            fact = VerificationFact.example(passed=False, evidence_ref=None)
            ledger.start(fact)
            print(json.dumps({"run_id":fact.run_id, "attempt_id":fact.attempt_id, "crash_stage":"before_verification"}), flush=True)
            # Simulate abrupt worker termination *after committing task facts*.
            os._exit(91)
        if args.save_session:
            session = create_native_session()
            session.state["poc_marker"] = "native-session-kept-across-processes"
            revision = store.save(args.save_session,session,fingerprint=FINGERPRINT)
            print(json.dumps({"saved": True, "revision":revision}))
            return 0
        if args.load_session:
            session, revision = store.load(args.load_session,fingerprint=FINGERPRINT)
            passed = session.state.get("poc_marker") == "native-session-kept-across-processes"
            print(json.dumps({"restored":passed,"revision":revision}))
            return 0 if passed else 1
        run_id = args.resume_pure or args.mark_unknown
        if not args.expected_attempt:
            raise ValueError("--expected-attempt required when recovering")
        if args.mark_unknown:
            # Deliberately no speculative externally dispatched write:
            # the test suite changes side_effect_class to NON_RETRYABLE
            # before invoking this option.
            result = RecoveryCoordinator(dsn).recover(run_id, interrupted_attempt_id=args.expected_attempt)
            print(json.dumps({"decision":result.outcome,"run_id":run_id}))
            return 0 if result.outcome == "RECONCILIATION" else 1
        result = RecoveryCoordinator(dsn).recover(run_id, interrupted_attempt_id=args.expected_attempt)
        if result.outcome != "STEP_BOUNDARY_RETRY" or not result.fact or not result.execution_id:
            print(json.dumps({"decision":result.outcome,"run_id":run_id}))
            return 1
        outcome = asyncio.run(run_document_case("expected",result.fact))
        ledger.finish(result.fact,outcome,result.execution_id)
        facts = ledger.read(run_id)
        passed = (
            facts["run"]["state"] == "COMPLETED"
            and [x["state"] for x in facts["attempts"]] == ["FAILED","SUCCEEDED"]
        )
        print(json.dumps({"decision":result.outcome,"completed":passed,
                          "attempts":len(facts["attempts"])}))
        return 0 if passed else 1
    except Exception as exc:
        # Avoid exposing native payload, database secret, or model context.
        print(f"ERROR: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
