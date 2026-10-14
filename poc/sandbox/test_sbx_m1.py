"""SBX-M1 test-first: synthetic adapter contract, not real Cube."""
import unittest
from types import SimpleNamespace
from uuid import uuid4
from poc.sandbox.sbx_management import CubeNativeCreateTransport, SandboxCreateService, SandboxConflict, SandboxPermissionDenied, SandboxUnknown

class FakeCube:
    def __init__(self):
        self.prefix=uuid4().hex[:10]; self.created=[]; self.commands=[]; self.fail_create=False; self.fail_command=False; self.exit_code=0
    def create(self, **kwargs):
        self.created.append(kwargs)
        if self.fail_create: raise TimeoutError("Cube ACK unknown")
        owner=self
        class Sandbox:
            sandbox_id="cube-"+owner.prefix+"-"+str(len(owner.created))
            commands=SimpleNamespace(run=owner.command)
        return Sandbox()
    def command(self, cmd, *, cwd, timeout):
        self.commands.append((cmd,cwd,timeout))
        if self.fail_command: raise TimeoutError("command ACK unknown")
        return SimpleNamespace(stdout="ok",stderr="",exit_code=self.exit_code)

class FakeStore:
    def __init__(self): self.rows={}
    def begin(self,*,scope,principal,key,fingerprint,template_id):
        k=(scope,principal,key)
        if k not in self.rows:
            self.rows[k]=dict(operation_id="op-"+uuid4().hex,scope=scope,principal=principal,key=key,fingerprint=fingerprint,template_id=template_id,state="PENDING",sandbox_id=None,exit_code=None)
        elif self.rows[k]["fingerprint"] != fingerprint: raise SandboxConflict("different request")
        return dict(self.rows[k])
    def get(self,op,scope,principal):
        for r in self.rows.values():
            if r["operation_id"]==op:
                if (r["scope"],r["principal"]) != (scope,principal): raise KeyError(op)
                return dict(r)
        raise KeyError(op)
    def transition(self,op,scope,principal,expected,state,**values):
        r=self.get(op,scope,principal)
        if r["state"]!=expected: raise SandboxConflict("stale")
        for v in self.rows.values():
            if v["operation_id"]==op: v.update(state=state,**values); return dict(v)
        raise KeyError(op)

class SBXM1Contract(unittest.TestCase):
    def setUp(self):
        self.cube=FakeCube(); self.db=FakeStore()
        self.svc=SandboxCreateService(self.db,CubeNativeCreateTransport(sdk=self.cube),
            authorize=lambda scope,principal,action,native: scope=="s1" and principal=="u1" and action=="create")
    def create(self, key="request-1",cube=None,commands=None,principal="u1"):
        return self.svc.create(scope="s1",principal=principal,idempotency_key=key,cube=cube or {"template":"tpl-test","timeout":3600},on_create=commands or [])
    def test_create_native_template_and_guest_command(self):
        r=self.create(commands=[{"command":"git --version","cwd":"/workspace","timeoutSeconds":30}])
        self.assertEqual(r["state"],"READY")
        self.assertEqual(self.cube.created[0]["template"],"tpl-test")
        self.assertEqual(self.cube.created[0]["timeout"],3600)
        self.assertEqual(self.cube.commands,[("git --version","/workspace",30)])
        self.assertEqual(self.cube.created[0]["metadata"]["harness_sbx_operation_id"],r["operation_id"])
    def test_idempotent_retry_and_conflict(self):
        one=self.create(); self.assertEqual(self.create()["operation_id"],one["operation_id"])
        self.assertEqual(len(self.cube.created),1)
        with self.assertRaises(SandboxConflict):
            self.create(cube={"template":"tpl-changed"})
    def test_create_ack_unknown_does_not_allocate_twice(self):
        self.cube.fail_create=True
        with self.assertRaises(SandboxUnknown): self.create()
        self.cube.fail_create=False
        self.assertEqual(self.create()["state"],"UNKNOWN")
        self.assertEqual(len(self.cube.created),1)
    def test_init_failure_is_not_ready(self):
        self.cube.exit_code=7
        r=self.create(commands=[{"command":"false","cwd":"/workspace","timeoutSeconds":10}])
        self.assertEqual((r["state"],r["exit_code"]),("FAILED",7))
    def test_command_unknown_is_not_replayed(self):
        self.cube.fail_command=True
        cmd=[{"command":"touch /workspace/x","cwd":"/workspace","timeoutSeconds":30}]
        with self.assertRaises(SandboxUnknown): self.create(commands=cmd)
        self.cube.fail_command=False
        self.assertEqual(self.create(commands=cmd)["state"],"UNKNOWN")
        self.assertEqual(len(self.cube.commands),1)
    def test_reject_untrusted_params_and_noncanonical_workdir_before_effect(self):
        for native in ({"template":"latest"},{"template":"tpl-a","unknown":1},{"template":"tpl-a","metadata":{"harness_sbx_operation_id":"spoof"}}):
            with self.assertRaises(ValueError): self.create(key=uuid4().hex,cube=native)
        for cwd in ("/etc","/workspace/../etc","/workspace//tmp"):
            with self.assertRaises(ValueError):
                self.create(key=uuid4().hex,commands=[{"command":"pwd","cwd":cwd,"timeoutSeconds":30}])
        self.assertFalse(self.cube.created)
    def test_authorization_and_scope(self):
        with self.assertRaises(SandboxPermissionDenied): self.create(principal="other")
        self.assertFalse(self.cube.created)
        r=self.create()
        with self.assertRaises(KeyError): self.db.get(r["operation_id"],"s2","u1")

if __name__=="__main__": unittest.main()