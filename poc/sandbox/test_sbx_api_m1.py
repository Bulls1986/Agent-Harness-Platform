"""API regression: this is an injected test identity, not production auth."""
import unittest
from types import SimpleNamespace
from fastapi.testclient import TestClient
from poc.sandbox.sbx_api import create_sbx_m1_app
from poc.sandbox.sbx_management import CubeNativeCreateTransport, SandboxCreateService
from poc.sandbox.test_sbx_m1 import FakeCube, FakeStore

class SandboxAPIContract(unittest.TestCase):
    def setUp(self):
        self.native=FakeCube()
        store=FakeStore()
        service=SandboxCreateService(store,CubeNativeCreateTransport(sdk=self.native),
            authorize=lambda scope,principal,action,cube: principal=="u1" and scope=="s1" and action=="create")
        self.client=TestClient(create_sbx_m1_app(
            resolve_context=lambda request: SimpleNamespace(
                principal_id=request.headers.get("Test-Principal","u1"),
                project_scope=request.headers.get("Test-Scope","s1")),
            service=service))

    def payload(self):
        return {"cube":{"template":"tpl-test","timeout":100},
            "onCreate":{"commands":[{"command":"git --version","cwd":"/workspace","timeoutSeconds":20}]}}

    def test_create_and_operation_query(self):
        res=self.client.post("/api/v1/sandboxes",json=self.payload(),
            headers={"Idempotency-Key":"key1"})
        self.assertEqual(res.status_code,202)
        obj=res.json()
        self.assertEqual(obj["state"],"READY")
        self.assertNotIn("principal",obj)
        op=self.client.get("/api/v1/sandbox-operations/"+obj["operationId"])
        self.assertEqual(op.status_code,200)
        self.assertEqual(op.json(),obj)
        self.assertEqual(self.client.post("/api/v1/sandboxes",json=self.payload(),
            headers={"Idempotency-Key":"key1"}).json(),obj)
        self.assertEqual(len(self.native.created),1)
        self.assertEqual(self.native.commands, [("git --version","/workspace",20)])

    def test_missing_key_scope_and_unauthorized(self):
        self.assertEqual(self.client.post("/api/v1/sandboxes",json=self.payload()).status_code,400)
        self.assertEqual(self.client.post("/api/v1/sandboxes",json=self.payload(),
            headers={"Idempotency-Key":"x","Test-Principal":"not-authorized"}).status_code,403)
        ok=self.client.post("/api/v1/sandboxes",json=self.payload(),
            headers={"Idempotency-Key":"x"}).json()
        self.assertEqual(self.client.get("/api/v1/sandbox-operations/"+ok["operationId"],
            headers={"Test-Scope":"different"}).status_code,404)

    def test_no_native_metadata_escape(self):
        data=self.payload();data["cube"]["metadata"]={"harness_sbx_scope_digest":"spoof"}
        self.assertEqual(self.client.post("/api/v1/sandboxes",json=data,
            headers={"Idempotency-Key":"x"}).status_code,422)
        self.assertEqual(self.native.created,[])

if __name__=="__main__": unittest.main()