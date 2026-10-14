"""SBX-M1 native Template SDK contracts (no separate template DSL)."""
import unittest
from types import SimpleNamespace
from poc.sandbox.sbx_management import CubeNativeCreateTransport, SandboxCreateService, SandboxPermissionDenied, SandboxConflict
from poc.sandbox.test_sbx_m1 import FakeCube, FakeStore
from poc.sandbox.sbx_template import CubeTemplateGateway

class FakeNativeTemplate:
    def __init__(self):
        self.entries={
            "tpl-alice":SimpleNamespace(template_id="tpl-alice",name="node-dev",status="READY",image_info="node@sha256:aaaa",job_id=""),
            "tpl-bad":SimpleNamespace(template_id="tpl-bad",name="",status="FAILED",image_info="",job_id=""),
        }
        self.builds=[];self.deletes=[];self.aliases=[]
    def list(self): return list(self.entries.values())
    def get(self,ref):
        for t in self.entries.values():
            if ref in (t.template_id,t.name) and ref: return t
        raise KeyError(ref)
    def build(self,**kwargs):
        self.builds.append(kwargs)
        return SimpleNamespace(template_id="tpl-new",job_id="job-new",status="PENDING")
    def delete(self,template_id): self.deletes.append(template_id)
    def set_alias(self,template_id,alias):
        self.aliases.append((template_id,alias))
        self.entries[template_id].name=alias
        return self.entries[template_id]

class NativeTemplateTests(unittest.TestCase):
    def setUp(self):
        self.sdk=FakeNativeTemplate()
        self.native=CubeTemplateGateway(sdk=self.sdk,authorize=lambda s,p,a,data: s=="s1" and p=="operator" and a in ("list","get","build","delete","alias","resolve"))
    def test_list_and_detail_are_native_metadata(self):
        rows=self.native.list(scope="s1",principal="operator")
        self.assertEqual(len(rows),2)
        self.assertEqual(self.native.get(scope="s1",principal="operator",template="tpl-alice")["template_id"],"tpl-alice")
        with self.assertRaises(SandboxPermissionDenied): self.native.list(scope="s1",principal="other")
    def test_alias_freezes_native_ready_id(self):
        self.assertEqual(self.native.resolve("node-dev"),"tpl-alice")
        self.assertEqual(self.native.resolve("tpl-alice"),"tpl-alice")
        with self.assertRaises(ValueError): self.native.resolve("tpl-bad")
        with self.assertRaises(ValueError): self.native.resolve("unknown")
    def test_build_uses_native_kwargs_only_and_separate_admin_policy(self):
        r=self.native.build(scope="s1",principal="operator",cube={
            "image":"ghcr.io/example/cube-base:1","name":"my-runtime","exposed_ports":[49983],
            "probe_port":49983,"probe_path":"/health","writable_layer_size":"1G"})
        self.assertEqual(r["template_id"],"tpl-new")
        self.assertEqual(self.sdk.builds[0]["image"],"ghcr.io/example/cube-base:1")
        with self.assertRaises(ValueError):
            self.native.build(scope="s1",principal="operator",cube={"dockerfile":"RUN git --version"})
        with self.assertRaises(ValueError):
            self.native.build(scope="s1",principal="operator",cube={"image":"abc","packages":{"apt":["git"]}})
        with self.assertRaises(SandboxPermissionDenied):
            self.native.build(scope="s1",principal="user",cube={"image":"abc"})
        self.assertEqual(len(self.sdk.builds),1)
    def test_delete_alias_requires_admin(self):
        self.native.set_alias(scope="s1",principal="operator",template="tpl-alice",alias="new-alias")
        self.assertEqual(self.sdk.aliases,[("tpl-alice","new-alias")])
        self.native.delete(scope="s1",principal="operator",template="tpl-alice")
        self.assertEqual(self.sdk.deletes,["tpl-alice"])
        with self.assertRaises(SandboxPermissionDenied):
            self.native.delete(scope="s1",principal="other",template="tpl-alice")
    def test_service_resolves_alias_but_retains_first_native_template_on_retry(self):
        cube=FakeCube();db=FakeStore()
        service=SandboxCreateService(db,CubeNativeCreateTransport(sdk=cube),
            authorize=lambda *_:True,template_resolver=self.native.resolve)
        kw=dict(scope="s1",principal="operator",idempotency_key="one",
                cube={"template":"node-dev","timeout":30},on_create=[])
        one=service.create(**kw)
        self.assertEqual(one["template_id"],"tpl-alice")
        self.assertEqual(cube.created[0]["template"],"tpl-alice")
        self.sdk.entries["tpl-alice"].name="moved"
        self.sdk.entries["tpl-other"]=SimpleNamespace(template_id="tpl-other",name="node-dev",status="READY",image_info="",job_id="")
        twice=service.create(**kw)
        self.assertEqual(twice["operation_id"],one["operation_id"])
        self.assertEqual(len(cube.created),1)
        # Alias may later disappear; idempotent reads must not re-resolve.
        del self.sdk.entries["tpl-other"]
        again=service.create(**kw)
        self.assertEqual(again["template_id"],"tpl-alice")
        self.assertEqual(len(cube.created),1)

if __name__=="__main__":unittest.main()