"""Real DEV-M5 containment: abort an in-flight OpenCode Guest by destroying
the original Cube MicroVM, NOT by granting a new Worker ambiguous execution.

Only synthetic payload and a locally authorized development Cube deployment.
The Native Session/Workspace is intentionally LOST after containment; external
side-effects remain UNKNOWN pending independent reconciliation. Do not claim
recoverable Worker handoff for this path.
"""
from __future__ import annotations

import json
import os
import secrets
import time
from uuid import uuid4

from poc.closed_loop.facts import PgFacts, UnsafeDispatch
from poc.sandbox.cube_binding import CubeBinding, CubeWorkspaceGateway, NativeCubeTransport
from poc.sandbox.opencode_bound_guest import BoundOpenCodeGuest


def main():
    for key in ("CUBE_API_URL", "CUBE_TEMPLATE_ID",
                "HARNESS_POC_DATABASE_URL"):
        if not os.environ.get(key):
            raise RuntimeError("QUARANTINE_LIVE_NOT_RUN: " + key)
    db=PgFacts()
    run_id="m5-containment-"+uuid4().hex
    execution_id="cube-exec-"+run_id
    scope="synthetic-scope-"+run_id
    workspace="synthetic-workspace-"+run_id
    frozen="sha256:synthetic-guest-containment"
    requested=db.create(run_id,prompt="synthetic OpenCode in-flight containment")
    db.dispatch(requested)
    db.bind(requested,"synthetic-verifier-"+run_id)
    binding=CubeBinding(db)
    gateway=CubeWorkspaceGateway(binding,NativeCubeTransport())
    binding.begin(
        execution_id=execution_id,run_id=run_id,scope=scope,
        workspace=workspace,environment_digest=frozen,
        owner_id="worker-A",fencing_epoch=7,lease_seconds=240)
    original=None
    contained=False
    try:
        original=gateway.allocate(execution_id,"worker-A",7)
        guest=BoundOpenCodeGuest(gateway,password=secrets.token_urlsafe(48))
        guest.start_server(execution_id,"worker-A",7)
        for i in range(20):
            try:
                session,prefix=guest.create_session(
                    execution_id,"worker-A",7)
                break
            except RuntimeError:
                if i==19:raise
                time.sleep(0.7)

        # The native OpenCode Shell request returns before its Guest process
        # exits. Deliberately leave the PG effect DISPATCHED to model a crash
        # or lost completion ACK; never assert the effect was successfully done.
        try:
            guest.native_shell(
                execution_id,"worker-A",7,session,prefix,
                "printf started > /workspace/m5-opencode/started.txt; "
                "sleep 45; printf late > /workspace/m5-opencode/late.txt")
        except RuntimeError as exc:
            # Native HTTP client has a 12s deadline while the real Guest
            # command sleeps 45s. The HTTP timeout is expected and proves
            # that B must NEVER treat an ambiguous ACK as safe to retry.
            if "Real Guest OpenCode HTTP request failed" not in str(exc):
                raise
            print("OPEN_CODE_NATIVE_HTTP_ACK_UNKNOWN",flush=True)
        for attempt in range(20):
            try:
                initial=gateway.read(
                    execution_id,"worker-A",7,
                    "/workspace/m5-opencode/started.txt")
            except UnsafeDispatch:
                raise
            except Exception:
                initial=None
            if initial=="started":
                break
            time.sleep(0.4)
        else:
            raise RuntimeError("OpenCode Guest command was not observed in-flight")
        try:
            gateway.read(execution_id,"worker-A",7,
                         "/workspace/m5-opencode/late.txt")
        except UnsafeDispatch:
            raise
        except Exception:
            pass
        else:
            raise RuntimeError("Guest in-flight command already finished")
        with db.tx() as c:
            c.execute(
                "UPDATE harness_cube_binding SET lease_expires_at="
                "now()-interval '1 second' WHERE execution_id=%s",
                (execution_id,))
        takeover_denied=False
        try:
            binding.takeover(
                execution_id,7,"worker-B",scope,workspace,frozen)
        except UnsafeDispatch:
            takeover_denied=True
        if not takeover_denied:
            raise UnsafeDispatch("Live unknown Guest command wrongly handed to B")
        gateway.quarantine_unresolved(
            execution_id,"worker-A",7,scope,workspace,frozen)
        contained=True
        if binding.get(execution_id).state!="RELEASED":
            raise UnsafeDispatch("Provider Destroy ACK not committed")
        if db.run_state(run_id)!="BLOCKED_UNKNOWN":
            raise UnsafeDispatch("Quarantined parent Run falsely remains executable")
        with db.tx() as c:
            rows=c.execute(
                "SELECT state FROM harness_cube_guest_effect "
                "WHERE execution_id=%s",(execution_id,)).fetchall()
        if rows!=[("DISPATCHED",)]:
            raise UnsafeDispatch("Unknown effect was falsely confirmed or removed")
        for _ in range(12):
            native=NativeCubeTransport().list()
            if not any(isinstance(x,dict) and x.get("sandboxID")==original
                       for x in native):
                break
            time.sleep(0.5)
        else:
            raise UnsafeDispatch("Original Cube Guest still exists after destroy")
        events=db.snapshot(run_id)["events"]
        if not any(e["type"]=="sandbox.guest.quarantine.contained"
                   for e in events):
            raise UnsafeDispatch("Quarantine outcome not recorded durably")
        print(json.dumps({
            "outcome": "PASS_REAL_OPENCODE_GUEST_INFLIGHT_CONTAINED",
            "run_id": run_id,
            "sandbox_id": original,
            "opencode_native_session_id": session,
            "real_guest_command_was_in_flight": True,
            "worker_b_takeover_rejected": takeover_denied,
            "provider_destroy_ack": "RELEASED",
            "native_guest_absent_after_destroy": True,
            "unknown_external_tool_effect": "RECONCILIATION_REQUIRED",
            "parent_run_state": "BLOCKED_UNKNOWN",
            "native_session_recovery": "NOT_ALLOWED_GUEST_DESTROYED",
        },sort_keys=True),flush=True)
    finally:
        if not contained and original:
            # Test-only emergency cleanup, not a Harness domain RELEASED ACK;
            # if native containment fails the real Run must stay unresolved.
            try:
                NativeCubeTransport().connect(original).kill()
                print("EMERGENCY_PROVIDER_TEARDOWN_REQUIRES_PG_RECONCILIATION",
                      flush=True)
            except Exception:
                print("EMERGENCY_PROVIDER_TEARDOWN_FAILED",flush=True)


if __name__=="__main__":
    main()
