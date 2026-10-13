"""Inspector new '能力验证' tab: real PostgreSQL evidence, no fake UI success.

The tab must explain use case, capability claim, necessary independent
proof, and unproven boundaries. It never launches Cube/SIGKILL operations
via an unauthenticated browser or interprets fake PG events as MicroVM proof.
"""
from __future__ import annotations

import os
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from poc.closed_loop.facts import PgFacts
from poc.closed_loop.inspector import create_app


@unittest.skipUnless(os.getenv("HARNESS_POC_DATABASE_URL"),
                     "Real PostgreSQL required; skips do not count as PASS")
class CapabilityTabTests(unittest.TestCase):
    def setUp(self):
        self.db=PgFacts()
        self.client=TestClient(create_app(
            facts_factory=lambda: PgFacts(),
            submit=lambda rid,prompt,command: None,
        ))

    def test_catalog_explains_use_capability_evidence_limits(self):
        res=self.client.get("/api/verification/scenarios")
        self.assertEqual(res.status_code,200,res.text)
        scenarios=res.json()["scenarios"]
        self.assertEqual([s["id"] for s in scenarios],[
            "agent-handoff","public-api-agent-run","cube-workspace",
            "worker-takeover","tool-receipt",
        ])
        for s in scenarios:
            for key in ("title","use_case","capability","execution_steps",
                        "required_evidence","limitations","availability"):
                self.assertTrue(s[key],(s["id"],key))
        self.assertEqual(scenarios[0]["availability"],"EXECUTABLE_EXISTING_TAB")
        self.assertEqual(scenarios[1]["id"],"public-api-agent-run")
        for s in scenarios[1:]:
            self.assertEqual(s["availability"],"READ_ONLY_NOT_EXECUTABLE")
            self.assertFalse(s["verified_by_inspector"])
        self.assertFalse(res.json()["production_ready"])

    def test_read_only_pg_evidence_returns_only_observed_not_claimed_pass(self):
        rid="inspector-ability-"+uuid4().hex
        key=self.db.create(rid,prompt="synthetic no-model-proof")
        self.db.dispatch(key)
        self.db.bind(key,"synthetic-native-"+rid)
        res=self.client.get("/api/verification/evidence/"+rid)
        self.assertEqual(res.status_code,200,res.text)
        data=res.json()
        self.assertEqual(data["run_id"],rid)
        self.assertEqual(data["provider_workflow_run_id"],"synthetic-native-"+rid)
        self.assertFalse(data["verified"])
        self.assertEqual(data["evidence_level"],"PERSISTED_FACTS_ONLY")
        self.assertIsNone(data["cube_binding"])
        self.assertEqual(data["observed_events"],["workflow.bound"])
        self.assertNotIn("synthetic no-model-proof",str(data))
        self.assertEqual(self.db.snapshot(rid)["state"],"RUNNING")

    def test_real_pg_cube_binding_must_not_claim_real_cube_proof(self):
        from poc.sandbox.cube_binding import CubeBinding
        rid="inspector-cube-"+uuid4().hex
        key=self.db.create(rid,prompt="synthetic binding")
        self.db.dispatch(key)
        self.db.bind(key,"native-"+rid)
        binding=CubeBinding(self.db)
        ex="execution-"+rid
        binding.begin(execution_id=ex,run_id=rid,scope="demo-scope",
                      workspace="demo-workspace",environment_digest="sha256:synthetic",
                      owner_id="worker-A",fencing_epoch=7)
        binding.claim_create(ex,"worker-A",7)
        binding.confirm(ex,"worker-A",7,"synthetic-not-real-cube")
        res=self.client.get("/api/verification/evidence/"+rid)
        self.assertEqual(res.status_code,200,res.text)
        data=res.json()
        self.assertEqual(data["cube_binding"]["sandbox_id"],"synthetic-not-real-cube")
        self.assertEqual(data["cube_binding"]["fencing_epoch"],7)
        self.assertEqual(data["cube_binding"]["workspace_ref"],"demo-workspace")
        self.assertEqual(data["cube_binding"]["state"],"ACTIVE")
        self.assertFalse(data["verified"])
        self.assertEqual(data["evidence_level"],"PERSISTED_FACTS_ONLY")

    def test_unknown_run_rejected_and_bad_ids_not_executed(self):
        self.assertEqual(self.client.get("/api/verification/evidence/missing-"+uuid4().hex).status_code,404)
        self.assertEqual(self.client.get("/api/verification/evidence/"+("a"*280)).status_code,422)
        self.assertEqual(self.client.post("/api/verification/scenarios/worker-takeover/start").status_code,404)

    def test_single_new_tab_in_existing_inspector_and_safe_dom(self):
        html=self.client.get("/")
        self.assertEqual(html.status_code,200)
        page=html.text
        self.assertIn('id="tab-agent-demo"',page)
        self.assertIn('id="tab-capabilities"',page)
        self.assertIn('id="view-capabilities"',page)
        self.assertIn('role="tablist"',page)
        self.assertIn("能力验证",page)
        self.assertIn('id="m7-capability-demo"',page)
        self.assertIn('id="m7-start"',page)
        self.assertIn("DEV-M7 · 公共 API 真实执行",page)
        self.assertEqual(page.count('role="tab"'),2)
        self.assertIn("需求分析与独立审核",page)
        self.assertIn("结构化需求",page)
        self.assertIn("使用场景",page)
        self.assertIn("证明什么能力",page)
        self.assertIn("实际验收证据",page)
        self.assertIn("不代表",page)
        self.assertIn("textContent",page)
        self.assertNotIn("innerHTML",page)


if __name__=="__main__":
    unittest.main()
