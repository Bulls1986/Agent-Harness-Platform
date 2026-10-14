"""DEV-SBX M1 Cube native Template admin API isolated from regular user."""
import unittest
from types import SimpleNamespace
from fastapi.testclient import TestClient
from poc.sandbox.sbx_api import create_sbx_m1_app
from poc.sandbox.sbx_management import CubeNativeCreateTransport,SandboxCreateService
from poc.sandbox.test_sbx_m1 import FakeCube,FakeStore
from poc.sandbox.test_sbx_template_m1 import FakeNativeTemplate
from poc.sandbox.sbx_template import CubeTemplateGateway

class TemplateAPIContract(unittest.TestCase):
    def setUp(self):
        self.sdk=FakeNativeTemplate()
        gateway=CubeTemplateGateway(sdk=self.sdk,authorize=lambda scope,principal,action,body:
            scope=="s1" and principal=="admin")
        self.client=TestClient(create_sbx_m1_app(
            resolve_context=lambda req:SimpleNamespace(
                project_scope="s1",principal_id=req.headers.get("Test-Principal","admin")),
            service=SandboxCreateService(FakeStore(),CubeNativeCreateTransport(sdk=FakeCube()),
                authorize=lambda *_:True, template_resolver=gateway.resolve),
            template_gateway=gateway))
    def test_admin_native_list_detail_build_alias_delete(self):
        a=self.client.get("/api/v1/cube/templates")
        self.assertEqual(a.status_code,200)
        self.assertEqual(len(a.json()),2)
        self.assertEqual(self.client.get("/api/v1/cube/templates/tpl-alice").json()["status"],"READY")
        a=self.client.post("/api/v1/cube/templates/build",json={"image":"ghcr.io/example/base:1","name":"test-base","probe_port":49983})
        self.assertEqual(a.status_code,202)
        self.assertEqual(a.json()["template_id"],"tpl-new")
        self.assertEqual(self.sdk.builds[0]["probe_port"],49983)
        a=self.client.put("/api/v1/cube/templates/tpl-alice/alias",json={"alias":"runtime-v2"})
        self.assertEqual(a.status_code,200)
        a=self.client.delete("/api/v1/cube/templates/tpl-alice")
        self.assertEqual(a.status_code,204)
        self.assertEqual(self.sdk.deletes,["tpl-alice"])
    def test_no_unprivileged_template_control_or_invented_dsl(self):
        hdr={"Test-Principal":"unprivileged"}
        for meth,path,payload in (
            ("get","/api/v1/cube/templates",None),
            ("get","/api/v1/cube/templates/tpl-alice",None),
            ("post","/api/v1/cube/templates/build",{"image":"example:1"}),
            ("put","/api/v1/cube/templates/tpl-alice/alias",{"alias":"new-base"}),
            ("delete","/api/v1/cube/templates/tpl-alice",None),
        ):
            with self.subTest(meth=meth,path=path):
                r=getattr(self.client,meth)(path,headers=hdr,**({"json":payload} if payload else {}))
                self.assertEqual(r.status_code,403)
        r=self.client.post("/api/v1/cube/templates/build",json={"dockerfile":"FROM base"})
        self.assertEqual(r.status_code,422)
        self.assertEqual(self.sdk.builds,[])
        self.assertEqual(self.sdk.deletes,[])

if __name__=="__main__":unittest.main()