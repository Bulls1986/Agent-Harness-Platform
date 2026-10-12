"""DEV-M5 real PostgreSQL authority contract for the Cube native SDK Port.

Fake transport verifies the calling contract ONLY, never isolation or MicroVM.
The optional real-Cube smoke gate is in verify_cube_live.py and must never
report success when no actual Cube endpoint/template is configured.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import unittest
from threading import Event
from unittest.mock import patch
from poc.closed_loop.facts import PgFacts, UnsafeDispatch
from poc.sandbox.cube_binding import CubeBinding, CubeWorkspaceGateway


class CountingCubeTransport:
    def __init__(self):
        self.created=[]
        self.connected=[]
        self.killed=[]
        self.files={}
        self.metadata={}
    def create(self,*,metadata):
        sandbox_id="cube-"+uuid4().hex
        self.created.append(sandbox_id)
        self.files[sandbox_id]={}
        self.metadata[sandbox_id]=dict(metadata)
        return sandbox_id
    def list(self):
        return [{"sandboxID":sid,"metadata":metadata}
                for sid,metadata in self.metadata.items()]
    def inspect(self,sandbox):
        return {"sandboxID":sandbox,"metadata":self.metadata[sandbox]}
    def connect(self, sandbox_id):
        self.connected.append(sandbox_id)
        if sandbox_id in self.killed or sandbox_id not in self.files:
            raise RuntimeError("Actual Cube sandbox missing")
        return sandbox_id
    def write(self, sandbox, path, data):
        self.files[sandbox][path]=data
    def read(self, sandbox, path):
        return self.files[sandbox][path]
    def kill(self, sandbox):
        self.killed.append(sandbox)


@unittest.skipUnless(os.environ.get("HARNESS_POC_DATABASE_URL"),
                     "Real PostgreSQL required: skip MUST NOT count as pass")
class CubePgBindingTests(unittest.TestCase):
    def setUp(self):
        self.db=PgFacts()
        self.transport=CountingCubeTransport()
        self.binding=CubeBinding(self.db)
        self.gateway=CubeWorkspaceGateway(self.binding,self.transport)
        self.rid="m5-cube-"+uuid4().hex
        key=self.db.create(self.rid,prompt="synthetic Cube workspace")
        self.db.dispatch(key)
        self.db.bind(key,"hatchet-"+self.rid)
        self.execution="exec-"+self.rid
        self.scope="scope-alpha-"+self.rid
        self.workspace="workspace-"+self.rid
        self.digest="sha256:synthetic-image-digest"
        self.binding.begin(
            execution_id=self.execution,run_id=self.rid,
            scope=self.scope,workspace=self.workspace,
            environment_digest=self.digest,owner_id="worker-A",
            fencing_epoch=7,lease_seconds=40,
        )

    def test_create_write_expiry_handoff_read_same_workspace(self):
        sb=self.gateway.allocate(self.execution,"worker-A",7)
        self.assertEqual(len(self.transport.created),1)
        self.gateway.write(self.execution,"worker-A",7,
                           "/workspace/proof.txt","persisted-cube-data")
        self.assertEqual(self.gateway.read(self.execution,"worker-A",7,
                                            "/workspace/proof.txt"),
                         "persisted-cube-data")
        # Verified PG-side lease expiry, not a caller-supplied timestamp.
        with self.db.tx() as c:
            c.execute("UPDATE harness_cube_binding SET lease_expires_at=now()-interval '1 second' "
                      "WHERE execution_id=%s",(self.execution,))
        with self.assertRaises(UnsafeDispatch):
            self.gateway.read(self.execution,"worker-A",7,"/workspace/proof.txt")
        b=self.binding.takeover(self.execution,expected_epoch=7,
                                new_owner="worker-B",scope=self.scope,
                                workspace=self.workspace,
                                environment_digest=self.digest)
        self.assertEqual(b.fencing_epoch,8)
        self.assertEqual(b.sandbox_id,sb)
        self.assertEqual(self.gateway.read(self.execution,"worker-B",8,
                                            "/workspace/proof.txt"),
                         "persisted-cube-data")
        self.assertIn(sb,self.transport.connected)
        self.assertEqual(len(self.transport.created),1)
        with self.assertRaises(UnsafeDispatch):
            self.gateway.write(self.execution,"worker-A",7,
                               "/workspace/proof.txt","stale")
        self.gateway.release(self.execution,"worker-B",8)
        self.assertEqual(self.transport.killed,[sb])
        with self.assertRaises(UnsafeDispatch):
            self.gateway.read(self.execution,"worker-B",8,
                              "/workspace/proof.txt")

    def test_scope_revision_and_expiry_reject_without_cube_side_effect(self):
        self.gateway.allocate(self.execution,"worker-A",7)
        baseline=len(self.transport.connected)
        for change in (
            {"scope":"other"}, {"workspace":"other"},
            {"environment_digest":"sha256:other"},
        ):
            with self.subTest(change),self.assertRaises(UnsafeDispatch):
                self.binding.takeover(self.execution,expected_epoch=7,
                                      new_owner="worker-B",**{
                                          "scope":self.scope,"workspace":self.workspace,
                                          "environment_digest":self.digest,**change})
        with self.assertRaises(UnsafeDispatch):
            self.gateway.write(self.execution,"worker-X",7,
                               "/workspace/forbidden","x")
        with self.assertRaises(UnsafeDispatch):
            self.gateway.write(self.execution,"worker-A",6,
                               "/workspace/forbidden","x")
        with self.assertRaises(UnsafeDispatch):
            self.gateway.read(self.execution,"worker-A",7,"/etc/passwd")
        with self.assertRaises(UnsafeDispatch):
            self.gateway.write(self.execution,"worker-A",7,
                               "/workspace/../etc/forbidden","x")
        self.assertEqual(len(self.transport.connected),baseline)

    def test_cube_connect_returns_wrong_provider_identity_must_fail_closed(self):
        sid=self.gateway.allocate(self.execution,"worker-A",7)
        self.assertEqual(self.binding.get(self.execution).sandbox_id,sid)
        # A faulty or compromised Provider could return another native Guest
        # despite being asked to connect the PG-authorized sandbox locator.
        self.transport.connect=lambda _requested: "another-cube-id"
        with self.assertRaises(UnsafeDispatch):
            self.gateway.read(
                self.execution,"worker-A",7,"/workspace/secret.txt")
        with self.assertRaises(UnsafeDispatch):
            self.gateway.write(
                self.execution,"worker-A",7,"/workspace/secret.txt","x")

    def test_cube_create_succeeds_but_pg_bind_ack_fails_no_second_create(self):
        # Crash-window: Cube MicroVM exists, but Harness PG binding ACK
        # is lost. A second allocate() MUST NEVER call Cube create again.
        native_confirm=self.binding.confirm
        def lost_pg_ack(*args,**kwargs):
            raise ConnectionError("Simulated PG confirmation ACK loss")
        self.binding.confirm=lost_pg_ack
        with self.assertRaises(UnsafeDispatch):
            self.gateway.allocate(self.execution,"worker-A",7)
        self.assertEqual(len(self.transport.created),1)
        self.assertIn(self.binding.get(self.execution).state,
                      ("CREATING","BLOCKED_UNKNOWN"))
        self.binding.confirm=native_confirm
        with self.assertRaises(UnsafeDispatch):
            self.gateway.allocate(self.execution,"worker-A",7)
        self.assertEqual(len(self.transport.created),1)
        # Deterministic read-only reconciliation of the original native ID.
        if self.binding.get(self.execution).state=="CREATING":
            self.binding.unknown(self.execution,"worker-A",7)
        recovered=self.gateway.reconcile_unknown(self.execution,"worker-A",7)
        self.assertEqual(recovered,self.transport.created[0])
        self.assertEqual(len(self.transport.created),1)

    def test_failed_create_cannot_blind_retry_or_fall_back_to_host(self):
        class MissingCube(CountingCubeTransport):
            def create(self,*,metadata): raise ConnectionError("Cube API unavailable")
        g=CubeWorkspaceGateway(self.binding,MissingCube())
        with self.assertRaises(UnsafeDispatch):
            g.allocate(self.execution,"worker-A",7)
        self.assertEqual(self.binding.get(self.execution).state,"BLOCKED_UNKNOWN")
        with self.assertRaises(UnsafeDispatch):
            g.allocate(self.execution,"worker-A",7)
        with self.assertRaises(UnsafeDispatch):
            g.read(self.execution,"worker-A",7,"/workspace/a")
        self.assertEqual(len(self.transport.created),0)

    def test_lost_create_ack_reconciles_existing_native_cube_without_reallocate(self):
        # Native Cube creation succeeds, but caller never persists its ACK.
        frozen=self.binding.correlation(self.execution)
        cube_id=self.transport.create(metadata=frozen)
        self.binding.unknown(self.execution,"worker-A",7)
        with self.assertRaises(UnsafeDispatch):
            self.gateway.allocate(self.execution,"worker-A",7)
        self.assertEqual(self.gateway.reconcile_unknown(
            self.execution,"worker-A",7),cube_id)
        self.assertEqual(self.binding.get(self.execution).sandbox_id,cube_id)
        self.assertEqual(self.binding.get(self.execution).state,"ACTIVE")
        self.assertEqual(len(self.transport.created),1)
        self.gateway.write(self.execution,"worker-A",7,
                           "/workspace/retain.txt","original")
        self.assertEqual(self.gateway.read(
            self.execution,"worker-A",7,"/workspace/retain.txt"),"original")
        self.assertEqual(self.gateway.reconcile_unknown(
            self.execution,"worker-A",7),cube_id)
        self.assertEqual(sum(e["type"]=="sandbox.binding.reconciled"
           for e in self.db.snapshot(self.rid)["events"]),1)

    def test_absent_duplicate_mismatch_or_unreadable_native_cube_stays_unknown(self):
        frozen=self.binding.correlation(self.execution)
        self.binding.unknown(self.execution,"worker-A",7)
        for entries in ([],[
            {"sandboxID":"cube-x","metadata":frozen},
            {"sandboxID":"cube-y","metadata":frozen},
        ],[
            {"sandboxID":"cube-other","metadata":{**frozen,"harness_scope":"other"}},
        ],[
            {"sandboxID":"cube-other","metadata":{**frozen,"harness_generation":"2"}},
        ],[
            {"sandboxID":"cube-other","metadata":None},
        ],[
            {"sandboxID":"cube-other","metadata":frozen},
            {"sandboxID":"cube-other","metadata":frozen},
        ]):
            with self.subTest(entries=entries):
                self.transport.list=lambda e=entries:e
                with self.assertRaises(UnsafeDispatch):
                    self.gateway.reconcile_unknown(self.execution,"worker-A",7)
                self.assertEqual(self.binding.get(self.execution).state,"BLOCKED_UNKNOWN")
        def broken(): raise TimeoutError("Cube listing unreliable")
        self.transport.list=broken
        with self.assertRaises(UnsafeDispatch):
            self.gateway.reconcile_unknown(self.execution,"worker-A",7)
        self.assertEqual(self.binding.get(self.execution).state,"BLOCKED_UNKNOWN")

    def test_worker_b_recovers_unknown_cube_after_creator_lost_ack(self):
        frozen=self.binding.correlation(self.execution)
        sid=self.transport.create(metadata=frozen)
        self.transport.write(sid,"/workspace/proof.txt","still-on-original-cube")
        self.binding.unknown(self.execution,"worker-A",7)
        with self.db.tx() as c:
            c.execute(
                "UPDATE harness_cube_binding "
                "SET lease_expires_at=now()-interval '1 second' "
                "WHERE execution_id=%s",(self.execution,))
        b=self.binding.takeover(
            self.execution,7,"worker-B",self.scope,self.workspace,self.digest)
        self.assertEqual(b.fencing_epoch,8)
        with self.assertRaises(UnsafeDispatch):
            self.gateway.reconcile_unknown(self.execution,"worker-A",7)
        resolved=self.gateway.reconcile_unknown(self.execution,"worker-B",8)
        self.assertEqual(resolved,sid)
        self.assertEqual(self.gateway.read(
            self.execution,"worker-B",8,"/workspace/proof.txt"),
            "still-on-original-cube")
        self.assertEqual(self.transport.created,[sid])
        with self.assertRaises(UnsafeDispatch):
            self.gateway.write(self.execution,"worker-A",7,
                               "/workspace/proof.txt","stale")

    def test_actual_cube_sdk_adapter_metadata_list_detail_contract(self):
        from unittest.mock import patch, MagicMock
        from poc.sandbox.cube_binding import NativeCubeTransport
        native=MagicMock()
        native.sandbox_id="sandbox-native"
        native.get_info.return_value={
            "sandboxID":"sandbox-native",
            "metadata":{"harness_execution_id":"ex"},
        }
        native.files.read.return_value="from-guest"
        with patch.dict(os.environ,{
            "CUBE_API_URL":"http://127.0.0.1:3000",
            "CUBE_TEMPLATE_ID":"tpl-synthetic",
        }):
            with patch("cubesandbox.Sandbox.create",return_value=native) as create:
                with patch("cubesandbox.Sandbox.list",return_value=[
                    {"sandboxID":"sandbox-native","metadata":{}}
                ]) as listing:
                    with patch("cubesandbox.Sandbox.connect",return_value=native) as connect:
                        transport=NativeCubeTransport()
                        self.assertEqual(
                            transport.create(metadata={"harness_execution_id":"ex"}),
                            "sandbox-native")
                        create.assert_called_once_with(
                            template="tpl-synthetic",timeout=300,
                            metadata={"harness_execution_id":"ex"})
                        self.assertEqual(len(transport.list()),1)
                        listing.assert_called_once_with()
                        sb=transport.connect("sandbox-native")
                        connect.assert_called_once_with("sandbox-native")
                        self.assertEqual(transport.inspect(sb),{
                            "sandboxID":"sandbox-native",
                            "metadata":{"harness_execution_id":"ex"},
                        })
                        self.assertEqual(transport.read(sb,"/workspace/abc"),
                                         "from-guest")

    def test_creator_crashes_in_creating_then_b_safely_reconciles(self):
        # Worker A may die after contacting Cube but before it marks UNKNOWN.
        metadata=self.binding.claim_create(self.execution,"worker-A",7)
        sid=self.transport.create(metadata=metadata)
        self.assertEqual(self.binding.get(self.execution).state,"CREATING")
        with self.db.tx() as c:
            c.execute("UPDATE harness_cube_binding "
                      "SET lease_expires_at=now()-interval '1 second' "
                      "WHERE execution_id=%s",(self.execution,))
        b=self.binding.takeover(
            self.execution,7,"worker-B",self.scope,self.workspace,self.digest)
        self.assertEqual(b.fencing_epoch,8)
        self.assertEqual(b.state,"BLOCKED_UNKNOWN")
        with self.assertRaises(UnsafeDispatch):
            self.gateway.allocate(self.execution,"worker-B",8)
        self.assertEqual(self.gateway.reconcile_unknown(
            self.execution,"worker-B",8),sid)
        self.assertEqual(self.transport.created,[sid])

    def test_native_create_propagates_frozen_metadata_not_caller_claim(self):
        self.gateway.allocate(self.execution,"worker-A",7)
        metadata=self.transport.metadata[self.transport.created[0]]
        self.assertEqual(metadata,self.binding.correlation(self.execution))
        self.assertEqual(metadata["harness_scope"],self.scope)
        self.assertEqual(metadata["harness_workspace_ref"],self.workspace)

    def test_parallel_owner_takeover_only_one_wins(self):
        self.gateway.allocate(self.execution,"worker-A",7)
        with self.db.tx() as c:
            c.execute("UPDATE harness_cube_binding SET lease_expires_at=now()-interval '1 second' "
                      "WHERE execution_id=%s",(self.execution,))
        def claim(owner):
            try:
                return CubeBinding(PgFacts()).takeover(
                    self.execution,expected_epoch=7,new_owner=owner,
                    scope=self.scope,workspace=self.workspace,
                    environment_digest=self.digest)
            except UnsafeDispatch:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(claim,("worker-B","worker-C")))
        self.assertEqual(len([r for r in results if r is not None]),1)
        self.assertEqual(self.binding.get(self.execution).fencing_epoch,8)

    def test_native_cube_requires_actual_endpoint_no_local_fallback(self):
        from unittest.mock import patch
        from poc.sandbox.cube_binding import NativeCubeTransport
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaisesRegex(RuntimeError,"Real CUBE_API_URL"):
                NativeCubeTransport()
        self.assertEqual(self.transport.created,[])

    def test_duplicate_allocation_and_release_unknown_are_non_retryable(self):
        sid=self.gateway.allocate(self.execution,"worker-A",7)
        with self.assertRaises(UnsafeDispatch):
            self.gateway.allocate(self.execution,"worker-A",7)
        self.assertEqual(self.transport.created,[sid])
        original_connect=self.transport.connect
        def unavailable(_):
            raise ConnectionError("Cube destroy ACK cannot be determined")
        self.transport.connect=unavailable
        with self.assertRaises(UnsafeDispatch):
            self.gateway.release(self.execution,"worker-A",7)
        self.assertEqual(self.binding.get(self.execution).state,"RELEASING")
        self.transport.connect=original_connect
        with self.assertRaises(UnsafeDispatch):
            self.gateway.allocate(self.execution,"worker-A",7)
        with self.assertRaises(UnsafeDispatch):
            self.gateway.read(self.execution,"worker-A",7,
                              "/workspace/proof.txt")
        self.assertEqual(len(self.transport.created),1)

    def test_missing_cube_on_connect_blocks_and_does_not_create_new_empty_one(self):
        sb=self.gateway.allocate(self.execution,"worker-A",7)
        self.gateway.write(self.execution,"worker-A",7,
                           "/workspace/proof.txt","needed")
        with self.db.tx() as c:
            c.execute("UPDATE harness_cube_binding SET lease_expires_at=now()-interval '1 second' "
                      "WHERE execution_id=%s",(self.execution,))
        self.binding.takeover(self.execution,7,"worker-B",self.scope,
                              self.workspace,self.digest)
        self.transport.killed.append(sb)
        with self.assertRaises(UnsafeDispatch):
            self.gateway.read(self.execution,"worker-B",8,
                              "/workspace/proof.txt")
        self.assertEqual(len(self.transport.created),1)

    def test_unresolved_guest_effect_blocks_takeover_even_after_lease_expires(self):
        """B must not reuse a Guest while A's async Shell may still run."""
        sid=self.gateway.allocate(self.execution,"worker-A",7)
        effect=self.binding.begin_guest_effect(
            self.execution,"worker-A",7,"OPENCODE_SHELL","sha256:test-intent")
        with self.db.tx() as c:
            c.execute("UPDATE harness_cube_binding "
                      "SET lease_expires_at=now()-interval '1 second' "
                      "WHERE execution_id=%s",(self.execution,))
        with self.assertRaises(UnsafeDispatch):
            self.binding.takeover(
                self.execution,7,"worker-B",
                self.scope,self.workspace,self.digest)
        self.assertEqual(self.binding.get(self.execution).sandbox_id,sid)
        self.assertEqual(self.binding.get(self.execution).fencing_epoch,7)
        self.assertEqual(self.binding.get_guest_effect(effect)["state"],"DISPATCHED")

    def test_confirmed_guest_effect_allows_normal_fenced_handoff(self):
        self.gateway.allocate(self.execution,"worker-A",7)
        effect=self.binding.begin_guest_effect(
            self.execution,"worker-A",7,"OPENCODE_SHELL","sha256:verified")
        self.binding.confirm_guest_effect(
            self.execution,"worker-A",7,effect,"sha256:receipt")
        self.assertEqual(self.binding.get_guest_effect(effect)["state"],"CONFIRMED")
        with self.db.tx() as c:
            c.execute("UPDATE harness_cube_binding "
                      "SET lease_expires_at=now()-interval '1 second' "
                      "WHERE execution_id=%s",(self.execution,))
        b=self.binding.takeover(
            self.execution,7,"worker-B",self.scope,self.workspace,self.digest)
        self.assertEqual(b.fencing_epoch,8)

    def test_guest_effect_wrong_owner_cannot_confirm_or_release(self):
        self.gateway.allocate(self.execution,"worker-A",7)
        effect=self.binding.begin_guest_effect(
            self.execution,"worker-A",7,"OPENCODE_SHELL","sha256:unknown")
        with self.assertRaises(UnsafeDispatch):
            self.binding.confirm_guest_effect(
                self.execution,"worker-B",7,effect,"sha256:fake")
        with self.assertRaises(UnsafeDispatch):
            self.binding.confirm_guest_effect(
                self.execution,"worker-A",8,effect,"sha256:fake")
        with self.assertRaises(UnsafeDispatch):
            self.gateway.release(self.execution,"worker-A",7)
        self.assertEqual(self.binding.get(self.execution).state,"ACTIVE")

    def test_actual_http_dispatch_race_blocks_worker_b_and_unknown_result(self):
        """Fake HTTP controls timing; PG lock/fence is genuine (not a Guest PASS)."""
        from poc.sandbox.opencode_bound_guest import BoundOpenCodeGuest
        started, finish = Event(), Event()
        self.gateway.allocate(self.execution,"worker-A",7)
        agent=BoundOpenCodeGuest(
            self.gateway,password="synthetic-only-private-secret-long-enough")
        def suspended_http(*args,**kwargs):
            started.set()
            if not finish.wait(8):
                raise TimeoutError("Synthetic HTTP transport expired")
            return {"data":{"synthetic":True}}
        with patch("poc.sandbox.opencode_bound_guest._guest_http",
                   side_effect=suspended_http):
            with ThreadPoolExecutor(max_workers=1) as pool:
                running=pool.submit(
                    agent.native_shell,self.execution,"worker-A",7,
                    "ses_realABC","/api",
                    "printf first > /workspace/m5-opencode/a.txt")
                try:
                    self.assertTrue(started.wait(5))
                    with self.db.tx() as c:
                        c.execute(
                            "UPDATE harness_cube_binding SET "
                            "lease_expires_at=now()-interval '1 second' "
                            "WHERE execution_id=%s",(self.execution,))
                    with self.assertRaises(UnsafeDispatch):
                        self.binding.takeover(
                            self.execution,7,"worker-B",
                            self.scope,self.workspace,self.digest)
                finally:
                    finish.set()
                with self.assertRaises(UnsafeDispatch):
                    running.result(timeout=10)
        with self.assertRaises(UnsafeDispatch):
            self.binding.takeover(
                self.execution,7,"worker-B",
                self.scope,self.workspace,self.digest)
        self.assertEqual(self.binding.get(self.execution).fencing_epoch,7)

    def test_trusted_quarantine_containment_destroys_original_guest_but_never_retries(self):
        sid=self.gateway.allocate(self.execution,"worker-A",7)
        effect=self.binding.begin_guest_effect(
            self.execution,"worker-A",7,"OPENCODE_SHELL","sha256:unsafe-inflight")
        with self.assertRaises(UnsafeDispatch):
            self.gateway.quarantine_unresolved(
                self.execution,"worker-A",7,self.scope,self.workspace,self.digest)
        with self.db.tx() as c:
            c.execute("UPDATE harness_cube_binding "
                      "SET lease_expires_at=now()-interval '1 second' "
                      "WHERE execution_id=%s",(self.execution,))
        with self.assertRaises(UnsafeDispatch):
            self.gateway.quarantine_unresolved(
                self.execution,"worker-A",7,"different-scope",self.workspace,self.digest)
        self.assertEqual(self.transport.killed,[])
        self.gateway.quarantine_unresolved(
            self.execution,"worker-A",7,self.scope,self.workspace,self.digest)
        self.assertEqual(self.transport.killed,[sid])
        self.assertEqual(self.binding.get(self.execution).state,"RELEASED")
        self.assertEqual(self.binding.get_guest_effect(effect)["state"],"DISPATCHED")
        self.assertEqual(self.db.run_state(self.rid),"BLOCKED_UNKNOWN")
        self.assertTrue(any(
            event["type"]=="run.blocked_unknown"
            for event in self.db.snapshot(self.rid)["events"]))
        self.assertEqual(len(self.transport.created),1)
        with self.assertRaises(UnsafeDispatch):
            self.binding.takeover(
                self.execution,7,"worker-B",self.scope,self.workspace,self.digest)

    def test_native_guest_effect_is_non_pure_even_without_m4_tool_journal(self):
        self.gateway.allocate(self.execution,"worker-A",7)
        effect=self.binding.begin_guest_effect(
            self.execution,"worker-A",7,"OPENCODE_SHELL","sha256:required")
        with self.db.tx() as c:
            self.assertTrue(PgFacts.has_non_pure_tool_intent(c,self.rid))
        self.binding.confirm_guest_effect(
            self.execution,"worker-A",7,effect,"sha256:verified")
        with self.db.tx() as c:
            self.assertTrue(PgFacts.has_non_pure_tool_intent(c,self.rid))

    def test_quarantine_wrong_native_identity_keeps_release_uncertain(self):
        sid=self.gateway.allocate(self.execution,"worker-A",7)
        self.binding.begin_guest_effect(
            self.execution,"worker-A",7,"OPENCODE_SHELL","sha256:unsafe-effect")
        with self.db.tx() as c:
            c.execute("UPDATE harness_cube_binding "
                      "SET lease_expires_at=now()-interval '1 second' "
                      "WHERE execution_id=%s",(self.execution,))
        self.transport.inspect=lambda _: {
            "sandboxID":"other-native-cube","metadata":{}}
        with self.assertRaises(UnsafeDispatch):
            self.gateway.quarantine_unresolved(
                self.execution,"worker-A",7,self.scope,self.workspace,self.digest)
        self.assertEqual(self.binding.get(self.execution).state,"RELEASING")
        self.assertNotIn(sid,self.transport.killed)

    def test_quarantine_accepts_native_provider_augmentation_but_not_identity_override(self):
        sid=self.gateway.allocate(self.execution,"worker-A",7)
        self.binding.begin_guest_effect(
            self.execution,"worker-A",7,"OPENCODE_SHELL","sha256:inflight")
        original_inspect=self.transport.inspect
        def supplemented_info(native):
            info=original_inspect(native)
            info["metadata"]={
                **info["metadata"],
                "cube_provider_runtime":"synthetic-extra",
                "cube_created_at":"synthetic-timestamp",
            }
            return info
        self.transport.inspect=supplemented_info
        with self.db.tx() as c:
            c.execute("UPDATE harness_cube_binding "
                      "SET lease_expires_at=now()-interval '1 second' "
                      "WHERE execution_id=%s",(self.execution,))
        self.gateway.quarantine_unresolved(
            self.execution,"worker-A",7,self.scope,self.workspace,self.digest)
        self.assertEqual(self.transport.killed,[sid])
        self.assertEqual(self.binding.get(self.execution).state,"RELEASED")

    def test_quarantine_native_critical_metadata_override_stays_unknown(self):
        sid=self.gateway.allocate(self.execution,"worker-A",7)
        self.binding.begin_guest_effect(
            self.execution,"worker-A",7,"OPENCODE_SHELL","sha256:inflight")
        original_inspect=self.transport.inspect
        def forged_info(native):
            info=original_inspect(native)
            info["metadata"]={
                **info["metadata"],"harness_scope":"forged-scope"}
            return info
        self.transport.inspect=forged_info
        with self.db.tx() as c:
            c.execute("UPDATE harness_cube_binding "
                      "SET lease_expires_at=now()-interval '1 second' "
                      "WHERE execution_id=%s",(self.execution,))
        with self.assertRaises(UnsafeDispatch):
            self.gateway.quarantine_unresolved(
                self.execution,"worker-A",7,self.scope,self.workspace,self.digest)
        self.assertEqual(self.binding.get(self.execution).state,"RELEASING")
        self.assertNotIn(sid,self.transport.killed)


if __name__=="__main__":
    unittest.main()
