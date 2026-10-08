"""A26 CI-only CLI: demonstrates waiting survives across independent processes.

This is not a public Approval API or IAM. It is deliberately restricted to
repository-owned POC fixtures and must never be exposed to end users.
"""
import argparse
import json
import os
from approval_wait import ApprovalWaitStore
from task_ledger import TaskLedger
from workflow_probe import VerificationFact


def main() -> int:
    parser=argparse.ArgumentParser()
    actions=parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--create",action="store_true")
    actions.add_argument("--inspect",metavar="RUN_ID")
    actions.add_argument("--approve",metavar="APPROVAL_ID")
    args=parser.parse_args()
    dsn=os.environ.get("POC_POSTGRES_DSN")
    if not dsn:
        raise RuntimeError("POC_POSTGRES_DSN required")
    TaskLedger(dsn).initialize()
    store=ApprovalWaitStore(dsn)
    if args.create:
        request=store.request(
            VerificationFact.example(passed=False,evidence_ref=None),
            requester_principal="poc-requester",
            approver_principal="poc-fixture-approver",
            action_ref="tool:external-write",resource_ref="resource:demo",
            policy_ref="policy:poc-approval",
        )
        print(json.dumps(vars(request)))
    elif args.inspect:
        print(json.dumps(vars(store.load_pending(args.inspect))))
    else:
        # Only this trusted CI harness supplies 'authorized=True'. Never use as
        # a production authorization shortcut; see external IAM contract.
        state=store.decide(args.approve,authenticated_principal="poc-fixture-approver",
                           authorized=True,decision="APPROVED")
        print(json.dumps({"run_state":state}))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
