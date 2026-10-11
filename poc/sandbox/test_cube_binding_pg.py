"""DEV-M5 real PostgreSQL authority contract for the Cube native SDK Port.

Fake transport verifies the calling contract ONLY, never isolation or MicroVM.
The optional real-Cube smoke gate is in verify_cube_live.py and must never
report success when no actual Cube endpoint/template is configured.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import unittest
from poc.closed_loop.facts import PgFacts, UnsafeDispatch
from poc.sandbox.cube_binding import CubeBinding, CubeWorkspaceGateway


class CountingCubeTransport:
    def __init__(self):
        self.created=[]
        self.connected=[]
        self.killed=[]
        self.files={}
    def create(self):
        sandbox_id="cube-"+uuid4().hex
        self.created.append(sandbox_id)
        self.files[sandbox_id]={}
        return sandbox_id
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

    def test_failed_create_cannot_blind_retry_or_fall_back_to_host(self):
        class MissingCube(CountingCubeTransport):
            def create(self): raise ConnectionError("Cube API unavailable")
        g=CubeWorkspaceGateway(self.binding,MissingCube())
        with self.assertRaises(UnsafeDispatch):
            g.allocate(self.execution,"worker-A",7)
        self.assertEqual(self.binding.get(self.execution).state,"BLOCKED_UNKNOWN")
        with self.assertRaises(UnsafeDispatch):
            g.allocate(self.execution,"worker-A",7)
        with self.assertRaises(UnsafeDispatch):
            g.read(self.execution,"worker-A",7,"/workspace/a")
        self.assertEqual(len(self.transport.created),0)

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


if __name__=="__main__":
    unittest.main()
