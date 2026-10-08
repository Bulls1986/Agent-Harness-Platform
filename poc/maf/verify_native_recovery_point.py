"""Real MAF FileCheckpointStorage -> PG RecoveryPoint -> separate Python restore.

Only uses public MAF Workflow/CheckpointStorage APIs. Native approval is
REJECTED so no sensitive execution. Does not recreate a finished Attempt.
Run with POC_POSTGRES_DSN set to a disposable test database.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
from native_hitl_probe import build,storage_at
from recovery_point_store import RecoveryPointRefs,RecoveryPointStore
from task_ledger import TaskLedger
from workflow_probe import VerificationFact

FINGERPRINT="maf-file-checkpoint-public-api-v1"
ENVIRONMENT="maf-test-restart-v1"


async def create(root:Path)->dict:
    store=storage_at(root)
    workflow=build(store)
    requests=[]
    async for event in workflow.run("ci-gated-action",stream=True):
        if event.type=="request_info":
            requests.append(event.request_id)
        elif event.type=="output":
            raise AssertionError("Premature tool output")
    if len(requests)!=1:
        raise AssertionError("One MAF pending request required")
    checkpoint=await store.get_latest(workflow_name=workflow.name)
    if checkpoint is None or not checkpoint.checkpoint_id:
        raise AssertionError("MAF public checkpoint not found")
    ledger=TaskLedger(os.environ["POC_POSTGRES_DSN"])
    ledger.initialize()
    fact=VerificationFact.example(passed=False,evidence_ref=None)
    ledger.start(fact)
    point=RecoveryPointStore(ledger.dsn).record(RecoveryPointRefs(
        run_id=fact.run_id,step_id=fact.step_id,attempt_id=fact.attempt_id,
        runtime_type="maf",runtime_checkpoint_ref=checkpoint.checkpoint_id,
        environment_fingerprint=ENVIRONMENT,provider_fingerprint=FINGERPRINT,
    ))
    return dict(run_id=fact.run_id,attempt_id=fact.attempt_id,
                native_request_id=requests[0],recovery_point_id=point)


async def resume(root:Path, data:dict, *,fingerprint:str=FINGERPRINT)->dict:
    dsn=os.environ["POC_POSTGRES_DSN"]
    point=RecoveryPointStore(dsn).choose(
        run_id=data["run_id"],attempt_id=data["attempt_id"],
        runtime_type="maf",provider_fingerprint=fingerprint,
        environment_fingerprint=ENVIRONMENT,
        checkpoint_capable=True,workspace_capable=False,
    )
    if point.outcome!="CANDIDATE_REQUIRES_PROVIDER_VERIFICATION":
        return {"outcome":point.outcome}
    store=storage_at(root)
    refs=await store.list_checkpoints(workflow_name=build(store).name)
    if point.runtime_checkpoint_ref not in {x.checkpoint_id for x in refs}:
        return {"outcome":"RECOVERY_UNAVAILABLE"}
    # Actually reconstruct native request from MAF's public checkpoint API.
    workflow=build(store)
    recovered=[]
    async for event in workflow.run(checkpoint_id=point.runtime_checkpoint_ref,stream=True):
        if event.type=="request_info":
            recovered.append(event.request_id)
        elif event.type=="output":
            raise AssertionError("Unexpected preapproval action after resume")
    if recovered != [data["native_request_id"]]:
        raise AssertionError("Native request changed across process")
    out=[]
    async for event in workflow.run(
        stream=True,responses={data["native_request_id"]:"REJECTED"}):
        if event.type=="output":
            out.append(event.data)
    if out!=["DENIED_NO_EXECUTION"]:
        raise AssertionError("MAF reject path returned wrong output")
    facts=TaskLedger(dsn).read(data["run_id"])
    return {
        "outcome":"RECOVERED_BY_REAL_MAF_PUBLIC_CHECKPOINT",
        "same_run":facts["run"]["run_id"]==data["run_id"],
        "same_attempt":len(facts["attempts"])==1 and
                       facts["attempts"][0]["attempt_id"]==data["attempt_id"],
        "same_request":recovered[0]==data["native_request_id"],
        "no_sensitive_execution":True,
    }


@unittest.skipUnless(os.environ.get("POC_POSTGRES_DSN"),"real PG required")
class NativeRecoveryPointProcessTests(unittest.TestCase):
    def test_native_checkpoint_ref_crosses_two_python_processes(self):
        with tempfile.TemporaryDirectory(prefix="maf-rp-provider-") as dir_name:
            root=Path(dir_name)
            a=subprocess.run(
                [sys.executable,__file__,"--phase","create","--root",str(root)],
                capture_output=True,text=True,timeout=40,
            )
            self.assertEqual(a.returncode,0,a.stderr[-1100:])
            created=json.loads(a.stdout)
            mismatch=subprocess.run(
                [sys.executable,__file__,"--phase","resume","--root",str(root),
                 "--data",json.dumps(created),"--fingerprint","wrong-sdk"],
                capture_output=True,text=True,timeout=40,
            )
            self.assertEqual(mismatch.returncode,0,mismatch.stderr[-1100:])
            self.assertEqual(json.loads(mismatch.stdout)["outcome"],"RECOVERY_INCOMPATIBLE")
            b=subprocess.run(
                [sys.executable,__file__,"--phase","resume","--root",str(root),
                 "--data",json.dumps(created)],
                capture_output=True,text=True,timeout=45,
            )
            self.assertEqual(b.returncode,0,b.stderr[-2100:])
            result=json.loads(b.stdout)
            self.assertEqual(result["outcome"],"RECOVERED_BY_REAL_MAF_PUBLIC_CHECKPOINT")
            self.assertTrue(result["same_run"])
            self.assertTrue(result["same_attempt"])
            self.assertTrue(result["same_request"])
            print(json.dumps({
                "outcome":result["outcome"],
                "separate_python_processes":True,
                "same_attempt":True,
                "incompatible_fingerprint_refused":True,
            },sort_keys=True))


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--phase",choices=("create","resume"))
    parser.add_argument("--root",type=Path)
    parser.add_argument("--data")
    parser.add_argument("--fingerprint",default=FINGERPRINT)
    args=parser.parse_args()
    if args.phase=="create":
        print(json.dumps(asyncio.run(create(args.root))))
    elif args.phase=="resume":
        print(json.dumps(asyncio.run(resume(args.root,json.loads(args.data),
                                           fingerprint=args.fingerprint))))
    else:
        unittest.main()


if __name__=="__main__":
    main()
