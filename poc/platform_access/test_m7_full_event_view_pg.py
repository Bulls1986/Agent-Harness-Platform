"""DEV-M7 frozen exit contract: real PG authorized public-client history.

Events for Tool / Approval / Artifact are SYNTHETIC typed platform facts:
they test M7 projection and access control, NOT M6 Approval/Tool execution.
Requires actual PostgreSQL and an independently composed Public API app,
never the local no-auth Inspector surface.
"""
from __future__ import annotations

import hashlib
import os
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from poc.closed_loop.facts import PgFacts
from poc.platform_access.authorized_reads import SecurityContext
from poc.platform_access.conversation_pg import PgConversationStore
from poc.platform_access.pg_reader import PgRunReader
from poc.platform_access.platform_api import create_platform_app


@unittest.skipUnless(os.getenv("HARNESS_POC_DATABASE_URL"), "Actual Harness PostgreSQL required")
class PublicClientEventContractPgTests(unittest.TestCase):
    def setUp(self):
        self.db=PgFacts()
        self.store=PgConversationStore(PgFacts())
        self.current=SecurityContext("user-demo","USER","project-demo")
        self.allowed=True
        self.app=create_platform_app(
            resolve_context=lambda request:self.current,
            reader=PgRunReader(PgFacts()),store=self.store,
            authorize=lambda *_:self.allowed,
            authorize_create=lambda *_:self.allowed,
            sse_max_polls=1,
        )
        self.client=TestClient(self.app)
        self.run_id="m7-events-"+uuid4().hex
        self.db.create(self.run_id,prompt="synthetic contract only",
                       project_scope="project-demo",initiator_principal_id="user-demo")
        self.cid=self.store.create_conversation("project-demo","user-demo","Synthetic events")
        self.tid=self.store.create_turn(self.cid,"Render persisted typed facts",
                                        "agent:synthetic@1","recipe:synthetic@1")
        self.store.link_run(self.tid,self.run_id)
        self.artifact_id="artifact-"+uuid4().hex
        self.store.register_artifact(
            self.artifact_id,self.run_id,"oss://private-bucket/test.pdf",
            hashlib.sha256(b"synthetic").hexdigest(),"application/pdf",9,
        )
        self.emit("response.output_text.delta",{"delta":"Hello from synthetic PG"})
        self.emit("tool.dispatched",{"tool":"file.read","operation":"synthetic"})
        self.emit("tool.outcome.unknown",{"tool":"file.read","state":"UNKNOWN"})
        self.emit("approval.requested",{"review_id":"approval-synthetic-1","state":"WAITING"})
        self.emit("approval.decision",{"review_id":"approval-synthetic-1","state":"APPROVED"})
        self.emit("artifact.created",{"artifact_id":self.artifact_id,
                                      "media_type":"application/pdf"})

    def emit(self,kind,data):
        with self.db.tx() as c: self.db.event(c,self.run_id,kind,data)

    def test_independent_authorized_api_reads_typed_events_and_refs(self):
        resp=self.client.get(f"/api/v1/conversations/{self.cid}")
        self.assertEqual(resp.status_code,200)
        self.assertEqual(resp.json()["turns"][0]["run_ids"],[self.run_id])
        resp=self.client.get(f"/api/v1/runs/{self.run_id}/events?after=0&limit=250")
        self.assertEqual(resp.status_code,200,resp.text)
        events=resp.json()["events"]
        self.assertEqual(
            [e["type"] for e in events[1:]],
            ["response.output_text.delta","tool.dispatched","tool.outcome.unknown",
             "approval.requested","approval.decision","artifact.created"]
        )
        stream=self.client.get(f"/api/v1/runs/{self.run_id}/stream")
        self.assertEqual(stream.status_code,200)
        for name in ("tool.dispatched","tool.outcome.unknown",
                     "approval.requested","approval.decision","artifact.created"):
            self.assertIn("event: "+name,stream.text)
        artifacts=self.client.get(f"/api/v1/runs/{self.run_id}/artifacts")
        self.assertEqual(artifacts.status_code,200)
        self.assertEqual(artifacts.json()["artifacts"][0]["artifact_id"],self.artifact_id)
        self.assertNotIn("oss://",artifacts.text)
        self.assertNotIn("oss://",stream.text)

    def test_all_pages_have_monotonic_cursor_and_late_revocation_denied(self):
        for index in range(253):
            self.emit("response.output_text.delta",{"delta":str(index)})
        first=self.client.get(f"/api/v1/runs/{self.run_id}/events?after=0&limit=250")
        self.assertEqual(first.status_code,200)
        self.assertEqual(len(first.json()["events"]),250)
        after=first.json()["cursor"]
        second=self.client.get(f"/api/v1/runs/{self.run_id}/events?after={after}&limit=250")
        self.assertEqual(second.status_code,200)
        self.assertGreater(len(second.json()["events"]),0)
        self.assertEqual(second.json()["events"][0]["seq"],after+1)
        self.assertEqual(second.json()["events"][-1]["seq"],self.db.events_since(self.run_id)[-1]["seq"]
                         if len(self.db.events_since(self.run_id))<250 else len(self.db.snapshot(self.run_id)["events"]))
        self.current=SecurityContext("user-foreign","USER","project-demo")
        self.assertEqual(self.client.get(f"/api/v1/runs/{self.run_id}/events?after={after}").status_code,404)
        self.assertEqual(self.client.get(f"/api/v1/runs/{self.run_id}/artifacts").status_code,404)
        self.current=SecurityContext("user-demo","USER","project-demo")
        self.allowed=False
        self.assertEqual(self.client.get(f"/api/v1/runs/{self.run_id}/stream").status_code,404)

    def test_readable_page_supports_tool_approval_artifact_and_paged_history(self):
        page=self.client.get(f"/ui/conversations/{self.cid}")
        self.assertEqual(page.status_code,200)
        html=page.text
        for label in ("工具事件","审核事件","文件事件","加载后续事件"):
            self.assertIn(label,html)
        self.assertIn("textContent",html)
        self.assertNotIn("innerHTML",html)
        self.assertNotIn("oss://private-bucket",html)
        self.assertNotIn("synthetic contract only",html)

if __name__=="__main__":
    unittest.main()
