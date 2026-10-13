"""Inspector DEV-M7 capability surface: real PostgreSQL + mounted public API.

TestClient uses a stub submit only to validate route composition; actual
Native Hatchet/SDK integration is a separate mandatory CI HTTP gate.
"""
from __future__ import annotations
import os
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from poc.closed_loop.facts import PgFacts
from poc.closed_loop.inspector import create_app
from poc.platform_access.authorized_reads import SecurityContext
from poc.platform_access.conversation_pg import PgConversationStore
from poc.platform_access.pg_reader import PgRunReader
from poc.platform_access.platform_api import create_platform_app


@unittest.skipUnless(os.getenv("HARNESS_POC_DATABASE_URL"),"Actual PostgreSQL mandatory")
class InspectorM7CapabilityPgTests(unittest.TestCase):
    def setUp(self):
        self.calls=[]
        self.context=SecurityContext("inspector-local-demo","USER","inspector-local-demo")
        def submit(rid,prompt,key):
            self.calls.append((rid,prompt,key))
        self.public=create_platform_app(
            resolve_context=lambda _:self.context,
            reader=PgRunReader(PgFacts()),
            store=PgConversationStore(PgFacts()),
            authorize=lambda ctx,binding,action: (
                ctx==self.context and binding.project_scope==self.context.project_scope
            ),
            authorize_create=lambda ctx,action:ctx==self.context,
            admit_recipe=lambda agent,recipe: (
                agent=="dual-sdk-requirements-review@v1"
                and recipe=="requirements-review@v1"
            ),
            start_run=submit,
            model_binding=lambda:("deterministic_local_model",None),
            sse_max_polls=1,
        )
        self.client=TestClient(create_app(
            facts_factory=PgFacts,submit=submit,public_api_app=self.public
        ))

    def test_existing_two_tabs_and_real_m7_capability_are_visible(self):
        page=self.client.get("/")
        self.assertEqual(page.status_code,200)
        self.assertIn('id="m7-capability-demo"',page.text)
        self.assertIn('id="m7-start"',page.text)
        self.assertIn("/m7-demo/api/v1",page.text)
        self.assertIn("Hatchet",page.text)
        self.assertIn("合成身份",page.text)
        self.assertNotIn("innerHTML",page.text)
        self.assertEqual(page.text.count('role="tab"'),2)
        capabilities=self.client.get("/api/verification/scenarios").json()
        item=next(s for s in capabilities["scenarios"] if s["id"]=="public-api-agent-run")
        self.assertEqual(item["availability"],"EXECUTABLE_M7_CAPABILITY_TAB")
        self.assertFalse(item["verified_by_inspector"])
        self.assertFalse(capabilities["production_ready"])

    def test_mounted_real_public_api_persists_conversation_turn_and_run(self):
        base="/m7-demo/api/v1"
        conv=self.client.post(base+"/conversations",json={
            "title":"Inspector synthetic "+uuid4().hex
        })
        self.assertEqual(conv.status_code,201,conv.text)
        cid=conv.json()["conversation_id"]
        turn=self.client.post(base+f"/conversations/{cid}/turns",json={
            "message":"Review synthetic product requirements",
            "agent_ref":"dual-sdk-requirements-review@v1",
            "recipe_ref":"requirements-review@v1"
        })
        self.assertEqual(turn.status_code,201,turn.text)
        tid=turn.json()["turn_id"]
        hdr={"Idempotency-Key":"inspector-"+uuid4().hex}
        a=self.client.post(base+f"/turns/{tid}/runs",headers=hdr)
        b=self.client.post(base+f"/turns/{tid}/runs",headers=hdr)
        self.assertEqual(a.status_code,202,a.text)
        self.assertEqual(b.status_code,202,b.text)
        rid=a.json()["run_id"]
        self.assertEqual(b.json()["run_id"],rid)
        self.assertTrue(b.json()["replayed"])
        self.assertEqual(len(self.calls),1)
        snap=self.client.get(base+"/runs/"+rid)
        self.assertEqual(snap.status_code,200,snap.text)
        self.assertEqual(snap.json()["state"],"CREATED")
        self.assertIsNone(snap.json()["result"])
        self.assertEqual(snap.json()["outbox"],"PENDING")
        self.assertEqual(self.client.get(base+f"/conversations/{cid}").json()
                         ["turns"][0]["run_ids"],[rid])
        events=self.client.get(base+f"/runs/{rid}/events")
        self.assertEqual(events.status_code,200)
        self.assertEqual(events.json()["events"][0]["type"],"run.created")
        self.assertEqual(self.client.get(base+f"/runs/{rid}/stream").status_code,200)
        # The original Inspector local demo continues to work independently.
        self.assertEqual(self.client.get("/api/runs/"+rid).status_code,200)

    def test_unsupported_recipe_or_identity_headers_do_not_gain_access(self):
        base="/m7-demo/api/v1"
        cid=self.client.post(base+"/conversations",json={"title":"no bypass"}).json()["conversation_id"]
        tid=self.client.post(base+f"/conversations/{cid}/turns",json={
            "message":"request","agent_ref":"other-agent",
            "recipe_ref":"unknown-recipe"
        }).json()["turn_id"]
        attempted=self.client.post(base+f"/turns/{tid}/runs",headers={
            "Idempotency-Key":"bad-"+uuid4().hex,
            "X-Principal-Id":"administrator","X-Project-Scope":"other"
        })
        self.assertEqual(attempted.status_code,404)
        self.assertEqual(len(self.calls),0)

    def test_unmounted_inspector_does_not_expose_demo_or_fake_availability(self):
        client=TestClient(create_app(facts_factory=PgFacts,submit=lambda *_:None))
        self.assertEqual(client.get("/m7-demo/api/v1/conversations").status_code,404)
        data=client.get("/api/verification/scenarios").json()
        item=next(s for s in data["scenarios"] if s["id"]=="public-api-agent-run")
        self.assertEqual(item["availability"],"READ_ONLY_NOT_EXECUTABLE")


if __name__=="__main__":
    unittest.main()
