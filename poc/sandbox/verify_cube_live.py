"""DEV-M5 actual Cube MicroVM verification.

Never return PASS or silently skip without real CUBE_API_URL,
CUBE_TEMPLATE_ID, CubeProxy access and PostgreSQL. No Docker fallback,
no fake SDK and no business data. The test creates a REAL Cube MicroVM.
"""
from __future__ import annotations
import json
import os
import traceback
from uuid import uuid4

from poc.closed_loop.facts import PgFacts,UnsafeDispatch
from poc.sandbox.cube_binding import (
    CubeBinding,CubeWorkspaceGateway,NativeCubeTransport,
)

def main():
    required=("CUBE_API_URL","CUBE_TEMPLATE_ID","HARNESS_POC_DATABASE_URL")
    absent=[key for key in required if not os.environ.get(key)]
    if absent:
        raise SystemExit("REAL_CUBE_GATE_NOT_RUN: missing "+",".join(absent))
    db=PgFacts()
    run_id="m5-cube-live-"+uuid4().hex
    command=db.create(run_id,prompt="synthetic real Cube MicroVM continuity")
    db.dispatch(command)
    db.bind(command,"synthetic-provider-"+run_id)
    eid="cube-exec-"+run_id
    scope="private-scope-"+run_id
    workspace="workspace-"+run_id
    digest="sha256:synthetic-frozen-environment"
    binding=CubeBinding(db)
    gateway=CubeWorkspaceGateway(binding,NativeCubeTransport())
    binding.begin(execution_id=eid,run_id=run_id,scope=scope,
                  workspace=workspace,environment_digest=digest,
                  owner_id="worker-A",fencing_epoch=7,lease_seconds=120)
    sid=None
    released=False
    try:
        sid=gateway.allocate(eid,"worker-A",7)
        text="microvm-kept-"+uuid4().hex
        gateway.write(eid,"worker-A",7,"/workspace/m5-reconnect.txt",text)
        assert gateway.read(eid,"worker-A",7,
                            "/workspace/m5-reconnect.txt")==text
        # Fault injection ONLY for the control-plane Lease, not the VM.
        # A fresh native Sandbox.connect from B must read A's same bytes.
        with db.tx() as c:
            c.execute("UPDATE harness_cube_binding "
                      "SET lease_expires_at=now()-interval '1 second' "
                      "WHERE execution_id=%s",(eid,))
        b=binding.takeover(eid,7,"worker-B",scope,workspace,digest,lease_seconds=90)
        assert b.sandbox_id==sid and b.fencing_epoch==8
        try:
            gateway.read(eid,"worker-A",7,"/workspace/m5-reconnect.txt")
        except UnsafeDispatch:
            pass
        else:
            raise AssertionError("STALE_WORKER_A_WAS_AUTHORIZED")
        # Completely new Cube SDK client and PG reader, same persisted locator.
        b_gateway=CubeWorkspaceGateway(CubeBinding(PgFacts()),NativeCubeTransport())
        actual=b_gateway.read(eid,"worker-B",8,"/workspace/m5-reconnect.txt")
        assert actual==text
        b_gateway.release(eid,"worker-B",8)
        released=True
        assert binding.get(eid).state=="RELEASED"
        print(json.dumps({
            "outcome":"PASS_REAL_CUBE_MICROVM",
            "run_id":run_id,
            "sandbox_id":sid,
            "workspace_ref":workspace,
            "native_reconnect":True,
            "worker_B_epoch":8,
            "read_original_bytes":True,
            "destroy_ack":"RELEASED",
            "physical_worker_SIGKILL":"NOT_TESTED_IN_THIS_CUBE_GATE",
            "cross_host":"NOT_TESTED",
        },sort_keys=True),flush=True)
    finally:
        if not released:
            # Cleanup only through persisted Cube locator, not Host Shell.
            # Unknown creation/destroy ACK needs explicit operator follow-up.
            try:
                fact=binding.get(eid)
                if fact.state=="ACTIVE" and fact.sandbox_id:
                    CubeWorkspaceGateway(binding,NativeCubeTransport()).release(
                        eid,fact.owner_id,fact.fencing_epoch)
            except Exception:
                print("CUBE_CLEANUP_UNCERTAIN: reconcile orphan before proceeding",
                      flush=True)

if __name__=="__main__":
    try:main()
    except Exception:
        traceback.print_exc()
        raise
