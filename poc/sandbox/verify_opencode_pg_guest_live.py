"""DEV-M5 actual PG fenced OpenCode public API in a persistent Cube Guest.

Run/Execution/Scope/Workspace/Environment are owned by Harness PostgreSQL,
Cube owns the original MicroVM, OpenCode owns its native Session and tools.
No Host Shell or synthetic Native transport is allowed. This verifies a
logical A->B handoff, NOT the separate physical SIGKILL / in-flight fence gate.
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
    for key in ("CUBE_API_URL", "CUBE_TEMPLATE_ID", "HARNESS_POC_DATABASE_URL"):
        if not os.environ.get(key):
            raise RuntimeError("REAL_OPENCODE_PG_LIVE_GATE_NOT_RUN: " + key)
    facts = PgFacts()
    rid = "m5-opencode-pg-" + uuid4().hex
    eid = "cube-exec-" + rid
    scope = "scope-" + rid
    workspace = "workspace-" + rid
    digest = "sha256:synthetic-opencode-v2-guest-frozen"
    original = "opencode-pg-guest-" + uuid4().hex
    secret = secrets.token_urlsafe(36)

    command = facts.create(rid, prompt="synthetic Cube OpenCode native tools")
    facts.dispatch(command)
    facts.bind(command, "synthetic-opencode-" + rid)
    binding = CubeBinding(facts)
    first = CubeWorkspaceGateway(binding, NativeCubeTransport())
    binding.begin(
        execution_id=eid, run_id=rid, scope=scope, workspace=workspace,
        environment_digest=digest, owner_id="worker-A",
        fencing_epoch=7, lease_seconds=600)
    released = False
    try:
        sid = first.allocate(eid, "worker-A", 7)
        agent_a = BoundOpenCodeGuest(first, password=secret)
        agent_a.start_server(eid, "worker-A", 7)
        for attempt in range(15):
            try:
                native_session_id, prefix = agent_a.create_session(
                    eid, "worker-A", 7)
                break
            except RuntimeError:
                if attempt == 14:
                    raise
                time.sleep(1)

        # This is the REAL native OpenCode Session Shell API. The file is
        # observed through the persisted Cube Workspace, not local disk.
        agent_a.native_shell_verified_file(
            eid, "worker-A", 7, native_session_id, prefix,
            "printf " + original + " > /workspace/m5-opencode/native-tool.txt",
            "/workspace/m5-opencode/native-tool.txt", original,
        )
        if agent_a.read_native_file(
                eid, "worker-A", 7, prefix, "native-tool.txt") != original:
            raise UnsafeDispatch("Native Files API and Cube Guest disagree")
        agent_a.native_vcs(eid, "worker-A", 7, prefix)

        # Durable correlation: native Session is a locator, not a permit.
        with facts.tx() as c:
            PgFacts.event(c, rid, "runtime.opencode.native.session", {
                "execution_id": eid, "sandbox_id": sid,
                "native_session_id": native_session_id,
                "api_prefix": prefix, "workspace_ref": workspace,
            })
            # Synthetic fault: trusted PG-controlled lease expiration only.
            c.execute(
                "UPDATE harness_cube_binding "
                "SET lease_expires_at=now()-interval '1 second' "
                "WHERE execution_id=%s", (eid,))

        wrong_scope_denied = False
        try:
            binding.takeover(
                eid, 7, "worker-B", "different-scope", workspace, digest)
        except UnsafeDispatch:
            wrong_scope_denied = True
        if not wrong_scope_denied:
            raise UnsafeDispatch("Wrong OpenCode Guest Scope was granted")

        transferred = binding.takeover(
            eid, 7, "worker-B", scope, workspace, digest, lease_seconds=240)
        if transferred.sandbox_id != sid or transferred.fencing_epoch != 8:
            raise UnsafeDispatch("OpenCode B did not take same Cube binding")
        stale_rejected = False
        try:
            agent_a.native_shell(
                eid, "worker-A", 7, native_session_id, prefix,
                "touch /workspace/m5-opencode/stale-should-not-appear")
        except UnsafeDispatch:
            stale_rejected = True
        if not stale_rejected:
            raise UnsafeDispatch("Stale OpenCode A was permitted Guest Shell")

        fresh_facts = PgFacts()
        fresh = CubeWorkspaceGateway(
            CubeBinding(fresh_facts), NativeCubeTransport())
        agent_b = BoundOpenCodeGuest(fresh, password=secret)
        persisted_events = fresh_facts.snapshot(rid)["events"]
        native_records = [
            event["data"] for event in persisted_events
            if event["type"] == "runtime.opencode.native.session"]
        if len(native_records) != 1:
            raise UnsafeDispatch("No unique durable OpenCode Session locator")
        saved = native_records[0]
        if (saved.get("sandbox_id") != sid
                or saved.get("workspace_ref") != workspace):
            raise UnsafeDispatch("Native OpenCode Session correlation altered")
        recovered = agent_b.recover_session(
            eid, "worker-B", 8, saved["native_session_id"], saved["api_prefix"])
        if recovered != native_session_id:
            raise UnsafeDispatch("B recovered a different Native Session")
        if agent_b.read_native_file(
                eid, "worker-B", 8, prefix, "native-tool.txt") != original:
            raise UnsafeDispatch("B lost original Guest File via OpenCode")
        agent_b.native_vcs(eid, "worker-B", 8, prefix)
        next_value = "worker-B-native-session-" + uuid4().hex
        agent_b.native_shell_verified_file(
            eid, "worker-B", 8, native_session_id, prefix,
            "printf " + next_value + " > /workspace/m5-opencode/b-proof.txt",
            "/workspace/m5-opencode/b-proof.txt", next_value,
        )
        if agent_b.read_native_file(
                eid, "worker-B", 8, prefix, "b-proof.txt") != next_value:
            raise UnsafeDispatch("B native OpenCode Files API did not see new data")
        fresh.release(eid, "worker-B", 8)
        released = True
        if binding.get(eid).state != "RELEASED":
            raise UnsafeDispatch("Cube native destroy ACK absent")
        print(json.dumps({
            "outcome": "PASS_REAL_PG_CUBE_OPENCODE_NATIVE_TOOLS_HANDOFF",
            "run_id": rid, "execution_id": eid,
            "sandbox_id": sid, "native_session_id": native_session_id,
            "native_opencode_shell_files_git": True,
            "native_session_id_after_takeover": recovered,
            "guest_original_file_preserved": True,
            "worker_a_epoch": 7, "worker_b_epoch": 8,
            "old_owner_denied": stale_rejected,
            "wrong_scope_denied": wrong_scope_denied,
            "destroy_ack": "RELEASED",
            "physical_worker_kill": "NOT_TESTED_IN_THIS_GATE",
            "in_flight_guest_fencing": "NOT_TESTED",
        }, sort_keys=True), flush=True)
    finally:
        if not released:
            try:
                fact = binding.get(eid)
                if fact.state == "ACTIVE" and fact.sandbox_id:
                    CubeWorkspaceGateway(
                        binding, NativeCubeTransport()).release(
                        eid, fact.owner_id, fact.fencing_epoch)
            except Exception:
                print("OPENCODE_GUEST_CLEANUP_UNKNOWN: reconcile Cube by PG",
                      rid, flush=True)


if __name__ == "__main__":
    main()
