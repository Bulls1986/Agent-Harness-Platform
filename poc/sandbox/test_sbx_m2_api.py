"""SBX-M2 HTTP routes use injected identity/permit; no production IAM claims."""
import os,unittest
from types import SimpleNamespace
from fastapi.testclient import TestClient
from poc.sandbox.test_sbx_m2 import AttachRealPostgres
from poc.sandbox.sbx_api import create_sbx_m1_app
from poc.sandbox.sbx_management import CubeNativeCreateTransport, SandboxCreateService
from poc.sandbox.test_sbx_m1 import FakeCube


@unittest.skipUnless(os.getenv("HARNESS_POC_DATABASE_URL"),"Real PG required; SKIP not PASS")
class AttachHTTPRealPG(AttachRealPostgres):
    def setUp(self):
        super().setUp()
        m1=SandboxCreateService(
            self.create,CubeNativeCreateTransport(sdk=FakeCube()),
            authorize=lambda *_:True)
        app=create_sbx_m1_app(
            service=m1, attach_service=self.svc,
            resolve_context=lambda req:SimpleNamespace(
                project_scope=req.headers.get("X-Test-Scope",self.scope),
                principal_id=req.headers.get("X-Test-Principal",self.principal)))
        self.http=TestClient(app)
    def payload(self):
        return {"sessionRef":"session-a","createOperationId":self.creation["operation_id"],
                "onAttach":{"commands":[{"command":"git --version","cwd":"/workspace","timeoutSeconds":30}]}}
    def test_http_attach_reconnect_and_binding_query(self):
        x=self.http.post("/api/v1/sandbox-bindings",json=self.payload(),
                         headers={"Idempotency-Key":"h1"})
        self.assertEqual(x.status_code,202,x.text)
        self.assertEqual(x.json()["state"],"ACTIVE")
        bid=x.json()["bindingId"]
        self.assertEqual(self.http.get("/api/v1/sandbox-bindings/"+bid).status_code,200)
        r=self.http.post("/api/v1/sandbox-bindings/"+bid+"/reconnect",
            json={"sessionRef":"session-a"})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(len(self.native.guest.calls),1)
        y=self.http.post("/api/v1/sandbox-bindings",json=self.payload(),
                         headers={"Idempotency-Key":"h1"})
        self.assertEqual(y.json()["bindingId"],bid)
        self.assertEqual(len(self.native.guest.calls),1)
        foreign=self.http.get("/api/v1/sandbox-bindings/"+bid,
            headers={"X-Test-Scope":"another"})
        self.assertEqual(foreign.status_code,404)
    def test_http_auth_conflict_and_invalid_command(self):
        self.assertEqual(self.http.post("/api/v1/sandbox-bindings",
            json=self.payload()).status_code,400)
        bad=self.payload()
        bad["sessionRef"]="not-authorized"
        self.assertEqual(self.http.post("/api/v1/sandbox-bindings",json=bad,
            headers={"Idempotency-Key":"x"}).status_code,403)
        bad=self.payload()
        bad["onAttach"]["commands"][0]["cwd"]="/etc"
        self.assertEqual(self.http.post("/api/v1/sandbox-bindings",json=bad,
            headers={"Idempotency-Key":"bad-cwd"}).status_code,422)
        self.assertEqual(self.native.connect_count,0)

if __name__=="__main__":unittest.main()