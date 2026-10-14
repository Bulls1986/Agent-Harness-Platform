"""SBX-M2 TDD: Session Attach / onAttach is pre-Run and fail-closed."""
import os
import unittest
from uuid import uuid4
from types import SimpleNamespace

from poc.sandbox.sbx_attach import PgSessionBindingStore, SessionAttachService, InitializationPermit
from time import time
from poc.sandbox.sbx_management import SandboxConflict, SandboxPermissionDenied, SandboxUnknown, PgSandboxCreateStore, SandboxCreateService, CubeNativeCreateTransport
from poc.sandbox.test_sbx_m1 import FakeCube
from poc.closed_loop.facts import PgFacts


class Guest:
    def __init__(self):
        self.calls=[]
        self.exit_code=0
        self.unknown=False
    def run(self,command,*,cwd,timeout):
        self.calls.append((command,cwd,timeout))
        if self.unknown: raise TimeoutError("Cube lost guest ACK")
        return SimpleNamespace(exit_code=self.exit_code,stdout="ok",stderr="")


class Native:
    def __init__(self):
        self.guest=Guest()
        self.connect_count=0
    def connect(self,sandbox_id):
        self.connect_count+=1
        return SimpleNamespace(commands=self.guest)


class FakeCreate:
    def __init__(self,scope,principal,sandbox):
        self.scope,self.principal,self.sandbox=scope,principal,sandbox
    def get(self,operation_id,scope,principal):
        if (operation_id,scope,principal)!=("create-1",self.scope,self.principal):
            raise KeyError(operation_id)
        return dict(operation_id=operation_id,scope=scope,principal=principal,
                    state="READY",sandbox_id=self.sandbox,template_id="tpl-frozen")


@unittest.skipUnless(os.environ.get("HARNESS_POC_DATABASE_URL"),"Real PostgreSQL required; SKIP not PASS")
class AttachRealPostgres(unittest.TestCase):
    def setUp(self):
        self.scope="sbx-m2-"+uuid4().hex
        self.principal="caller"
        self.native=Native()
        self.facts=PgFacts()
        self.store=PgSessionBindingStore(self.facts)
        self.create=PgSandboxCreateStore(self.facts)
        self.creation=SandboxCreateService(
            self.create,CubeNativeCreateTransport(sdk=FakeCube()),
            authorize=lambda *_:True).create(
                scope=self.scope,principal=self.principal,idempotency_key="make",
                cube={"template":"tpl-real"},on_create=[])
        self.sandbox=self.creation["sandbox_id"]
        self.allowed={"session-a"}
        self.actions=[]
        def permit(scope,principal,action,payload):
            self.actions.append(action)
            if scope!=self.scope or principal!=self.principal:
                return False
            if action=="attach":
                return True
            if action=="initialize":
                return InitializationPermit(
                    scope=scope,principal=principal,session_ref=payload["sessionRef"],
                    sandbox_id=payload["sandboxId"],
                    operation_digest=payload["operationDigest"],expires_at=time()+120)
            return False
        self.svc=SessionAttachService(
            store=self.store, create_store=self.create, native=self.native,
            authorize=permit,
            authorize_session=lambda scope,principal,session: session in self.allowed and scope==self.scope and principal==self.principal,
        )
    def attach(self,*,key="k1",session="session-a",commands=None,principal="caller",operation="create-1"):
        return self.svc.attach(scope=self.scope,principal=principal,
            create_operation_id=(self.creation["operation_id"] if operation=="create-1" else operation), session_ref=session,idempotency_key=key,
            on_attach=commands if commands is not None else [{
                "command":"git clone /workspace/remote.git /workspace/app",
                "cwd":"/workspace","timeoutSeconds":60},
                {"command":"git -C /workspace/app fetch origin",
                 "cwd":"/workspace","timeoutSeconds":60}])

    def test_first_attach_runs_two_commands_once_reconnect_is_read_only(self):
        a=self.attach()
        self.assertEqual(a["state"],"ACTIVE")
        self.assertEqual(a["sandbox_id"],self.sandbox)
        self.assertEqual(len(self.native.guest.calls),2)
        b=self.attach()
        self.assertEqual(b["binding_id"],a["binding_id"])
        self.assertEqual(len(self.native.guest.calls),2)
        c=self.svc.get(scope=self.scope,principal=self.principal,binding_id=a["binding_id"])
        self.assertEqual(c["state"],"ACTIVE")
        self.assertEqual(self.svc.reconnect(scope=self.scope,principal=self.principal,
            session_ref="session-a",binding_id=a["binding_id"])["binding_id"],a["binding_id"])
        self.assertEqual(len(self.native.guest.calls),2)

    def test_cross_session_and_changed_key_cannot_claim_writable_sandbox(self):
        self.attach()
        self.allowed.add("session-b")
        with self.assertRaises(SandboxConflict):
            self.attach(session="session-b",key="other",commands=[])
        with self.assertRaises(SandboxConflict):
            self.attach(key="k1",commands=[])
        self.assertEqual(len(self.native.guest.calls),2)

    def test_native_reconnect_failure_does_not_claim_live_session(self):
        b=self.attach(commands=[])
        self.native.connect=lambda sandbox_id: (_ for _ in ()).throw(
            RuntimeError("native Cube instance gone"))
        with self.assertRaises(SandboxUnknown):
            self.svc.reconnect(scope=self.scope,principal=self.principal,
                session_ref="session-a",binding_id=b["binding_id"])
        self.assertEqual(self.native.guest.calls,[])

    def test_unauthorized_session_and_unprivileged_init_cannot_dispatch(self):
        with self.assertRaises(SandboxPermissionDenied):
            self.attach(session="session-other")
        with self.assertRaises(SandboxPermissionDenied):
            self.attach(principal="stranger")
        self.assertEqual(self.native.connect_count,0)

    def test_unready_or_cross_scope_create_cannot_attach(self):
        with self.assertRaises(KeyError):
            self.attach(operation="absent")
        with self.assertRaises(KeyError):
            self.svc.get(scope="other-scope",principal=self.principal,binding_id="fake")
        self.assertEqual(self.native.connect_count,0)

    def test_command_nonzero_failed_and_no_replay(self):
        self.native.guest.exit_code=23
        a=self.attach()
        self.assertEqual(a["state"],"FAILED")
        self.assertEqual(a["exit_code"],23)
        self.native.guest.exit_code=0
        b=self.attach()
        self.assertEqual(b["state"],"FAILED")
        self.assertEqual(len(self.native.guest.calls),1)
        with self.assertRaises(SandboxConflict):
            self.svc.reconnect(scope=self.scope,principal=self.principal,
                session_ref="session-a",binding_id=a["binding_id"])

    def test_ambiguous_command_unknown_no_replay(self):
        self.native.guest.unknown=True
        with self.assertRaises(SandboxUnknown):
            self.attach()
        self.native.guest.unknown=False
        b=self.attach()
        self.assertEqual(b["state"],"UNKNOWN")
        self.assertEqual(len(self.native.guest.calls),1)

    def test_expired_or_mismatched_initialization_permit_rejected(self):
        old=self.svc.authorize
        for case in ("expired","wrong-sandbox","wrong-digest"):
            def issue(scope,principal,action,payload):
                if action=="attach":return True
                if action=="initialize":
                    return InitializationPermit(
                        scope=scope,principal=principal,
                        session_ref=payload["sessionRef"],
                        sandbox_id="different" if case=="wrong-sandbox" else payload["sandboxId"],
                        operation_digest="different" if case=="wrong-digest" else payload["operationDigest"],
                        expires_at=time()-1 if case=="expired" else time()+60)
                return False
            self.svc.authorize=issue
            with self.subTest(case=case),self.assertRaises(SandboxPermissionDenied):
                self.attach(key=uuid4().hex)
        self.svc.authorize=old
        self.assertEqual(self.native.connect_count,0)

    def test_revoked_session_cannot_read_or_reconnect_binding(self):
        b=self.attach(commands=[])
        self.allowed.clear()
        with self.assertRaises(SandboxPermissionDenied):
            self.svc.get(scope=self.scope,principal=self.principal,
                         binding_id=b["binding_id"])
        with self.assertRaises(SandboxPermissionDenied):
            self.svc.reconnect(scope=self.scope,principal=self.principal,
                         session_ref="session-a",binding_id=b["binding_id"])

    def test_interrupted_initializing_is_blocked_and_operator_reconcile_to_unknown(self):
        b=self.attach(commands=[])
        # Deliberately simulate a lost worker after persistent INITIALIZING
        # rather than sending a second side-effecting command.
        self.store.transition(binding_id=b["binding_id"],scope=self.scope,
            principal=self.principal,from_state="ACTIVE",to_state="INITIALIZING")
        with self.assertRaises(SandboxPermissionDenied):
            self.svc.reconcile(scope=self.scope,principal=self.principal,
                binding_id=b["binding_id"])
        previous=self.svc.authorize
        self.svc.authorize=lambda scope,principal,action,payload: (
            True if action=="reconcile" else previous(scope,principal,action,payload))
        updated=self.svc.reconcile(scope=self.scope,principal=self.principal,
            binding_id=b["binding_id"])
        self.assertEqual(updated["state"],"UNKNOWN")
        with self.assertRaises(SandboxConflict):
            self.svc.reconnect(scope=self.scope,principal=self.principal,
                session_ref="session-a",binding_id=b["binding_id"])
        self.assertEqual(self.native.guest.calls,[])

    def test_connection_and_workdir_policy_no_host_fallback(self):
        with self.assertRaises(ValueError):
            self.attach(commands=[{"command":"git pull","cwd":"/etc","timeoutSeconds":30}])
        self.assertEqual(self.native.connect_count,0)

if __name__=="__main__":
    unittest.main()