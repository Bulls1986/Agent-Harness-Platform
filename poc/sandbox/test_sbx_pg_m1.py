"""DEV-SBX M1 real PostgreSQL contract; no fake PG acceptance."""
import os
import unittest
from uuid import uuid4
from poc.closed_loop.facts import PgFacts
from poc.sandbox.sbx_management import (
    PgSandboxCreateStore, CubeNativeCreateTransport, SandboxCreateService,
    SandboxConflict, SandboxUnknown,
)
from poc.sandbox.test_sbx_m1 import FakeCube

@unittest.skipUnless(os.getenv("HARNESS_POC_DATABASE_URL"),
    "Real PostgreSQL URL required; SKIPPED is NOT a pass")
class SBXM1RealPostgres(unittest.TestCase):
    def setUp(self):
        self.store=PgSandboxCreateStore(PgFacts())
        self.cube=FakeCube()
        self.scope="scope-"+uuid4().hex
        self.svc=SandboxCreateService(self.store,CubeNativeCreateTransport(sdk=self.cube),
            authorize=lambda scope,principal,action,native: scope==self.scope and principal=="u1" and action=="create")
    def create(self,key="same",commands=None,template="tpl-test"):
        return self.svc.create(scope=self.scope,principal="u1",
            idempotency_key=key,cube={"template":template,"timeout":60},
            on_create=commands or [])
    def test_pg_create_reconnect_idempotency_and_scope_read(self):
        a=self.create()
        self.assertEqual(a["state"],"READY")
        other=PgSandboxCreateStore(PgFacts())
        b=other.begin(scope=self.scope,principal="u1",key="same",
            fingerprint=a["fingerprint"],template_id=a["template_id"])
        self.assertEqual(a["operation_id"],b["operation_id"])
        self.assertEqual(len(self.cube.created),1)
        self.assertEqual(other.get(a["operation_id"],self.scope,"u1")["sandbox_id"],a["sandbox_id"])
        with self.assertRaises(KeyError):
            other.get(a["operation_id"],"foreign-scope","u1")
        with self.assertRaises(SandboxConflict):
            self.create(template="tpl-other")
    def test_pg_unknown_create_is_durably_non_retryable(self):
        self.cube.fail_create=True
        with self.assertRaises(SandboxUnknown):
            self.create()
        self.assertEqual(len(self.cube.created),1)
        self.cube.fail_create=False
        state=self.create()
        self.assertEqual(state["state"],"UNKNOWN")
        self.assertEqual(self.store.get(state["operation_id"],self.scope,"u1")["state"],"UNKNOWN")
        self.assertEqual(len(self.cube.created),1)
    def test_pg_guest_command_failure_and_unknown(self):
        self.cube.exit_code=22
        cmd=[{"command":"exit 22","cwd":"/workspace","timeoutSeconds":5}]
        failure=self.create(key="failed",commands=cmd)
        self.assertEqual(failure["state"],"FAILED")
        self.assertEqual(failure["exit_code"],22)
        self.cube.fail_command=True
        with self.assertRaises(SandboxUnknown):
            self.create(key="unknown",commands=cmd)
        self.cube.fail_command=False
        again=self.create(key="unknown",commands=cmd)
        self.assertEqual(again["state"],"UNKNOWN")
        self.assertEqual(len(self.cube.commands),2)

if __name__=="__main__": unittest.main()