"""DEV-M7 original scope: real PG Conversation/Turn/Run + authorized SSE/Artifact UI."""
from __future__ import annotations
import hashlib
import os
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from poc.closed_loop.facts import PgFacts
from poc.platform_access.authorized_reads import SecurityContext
from poc.platform_access.pg_reader import PgRunReader
from poc.platform_access.conversation_pg import PgConversationStore
from poc.platform_access.platform_api import create_platform_app


@unittest.skipUnless(os.getenv("HARNESS_POC_DATABASE_URL"),"Real PG required; skipped tests are not acceptance")
class M7PlatformApiPgTests(unittest.TestCase):
    def setUp(self):
        self.db=PgFacts()
        self.store=PgConversationStore(PgFacts())
        self.a=SecurityContext("user-a","USER","project-a")
        self.same=SecurityContext("user-c","USER","project-a")
        self.b=SecurityContext("user-b","USER","project-b")
        self.current=self.a
        self.permissions=True
        self.policy_calls=[]
        def policy(context,binding,action):
            self.policy_calls.append((context.principal_id,action))
            return self.permissions
        self.client=TestClient(create_platform_app(
            resolve_context=lambda _:self.current,
            reader=PgRunReader(PgFacts()),store=self.store,
            authorize=policy,authorize_create=lambda _,action:self.permissions,
            sse_max_polls=1,cancel_run=PgFacts().request_cancel,
        ))
        self.run_a="m7-public-"+uuid4().hex
        self.run_b="m7-public-"+uuid4().hex
        self.db.create(self.run_a,prompt="secret-a",project_scope="project-a",
                       initiator_principal_id="user-a")
        self.db.create(self.run_b,prompt="secret-b",project_scope="project-b",
                       initiator_principal_id="user-b")
        self.db.dispatch(self.run_a+":segment-0:create:v1")
        self.db.bind(self.run_a+":segment-0:create:v1","wf-"+self.run_a)
        with self.db.tx() as c:
            self.db.event(c,self.run_a,"response.output_text.delta",
                          {"step_id":"pydantic","delta":"Hello from PG","runtime":"pydantic","source":"provider_stream"})

    def conversation(self):
        r=self.client.post("/api/v1/conversations",json={"title":"Synthetic review"})
        self.assertEqual(r.status_code,201,r.text)
        return r.json()["conversation_id"]

    def turn(self,cid):
        r=self.client.post(f"/api/v1/conversations/{cid}/turns",
                           json={"message":"Review synthetic specification",
                                 "agent_ref":"agent:analyst@1",
                                 "recipe_ref":"recipe:review@v1"})
        self.assertEqual(r.status_code,201,r.text)
        return r.json()["turn_id"]

    def test_conversation_turn_run_persisted_and_selection_readable(self):
        cid=self.conversation()
        turn=self.turn(cid)
        r=self.client.post(f"/api/v1/turns/{turn}/runs/{self.run_a}")
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(self.client.post(f"/api/v1/turns/{turn}/runs/{self.run_a}").status_code,200)
        detail=self.client.get(f"/api/v1/conversations/{cid}")
        self.assertEqual(detail.status_code,200,detail.text)
        self.assertEqual(detail.json()["turns"][0]["turn_id"],turn)
        self.assertEqual(detail.json()["turns"][0]["run_ids"],[self.run_a])
        self.assertEqual(detail.json()["turns"][0]["agent_ref"],"agent:analyst@1")
        self.assertEqual(detail.json()["turns"][0]["recipe_ref"],"recipe:review@v1")
        self.assertEqual(self.client.get("/api/v1/conversations").json()["conversations"][0]["conversation_id"],cid)
        self.assertEqual(self.client.get(f"/api/v1/runs/{self.run_a}").status_code,200)
        # New store process reads the same immutable facts.
        self.assertEqual(PgConversationStore(PgFacts()).conversation(cid)["turns"][0]["run_ids"],[self.run_a])

    def test_cross_project_and_same_project_other_user_fail_before_payload(self):
        cid=self.conversation()
        turn=self.turn(cid)
        self.client.post(f"/api/v1/turns/{turn}/runs/{self.run_a}")
        for actor in (self.same,self.b):
            self.current=actor
            for path in (f"/api/v1/conversations/{cid}",f"/api/v1/conversations/{cid}/turns",
                         f"/api/v1/turns/{turn}/runs/{self.run_a}",
                         f"/api/v1/runs/{self.run_a}",f"/api/v1/runs/{self.run_a}/events",
                         f"/api/v1/runs/{self.run_a}/stream",
                         f"/api/v1/runs/{self.run_a}/artifacts",f"/ui/conversations/{cid}"):
                method="post" if path.endswith("/turns") or "/runs/" in path and path.startswith("/api/v1/turns") else "get"
                r=(self.client.post(path,json={"message":"x","agent_ref":"synthetic","recipe_ref":"synthetic"})
                   if method=="post" else self.client.get(path))
                self.assertEqual(r.status_code,404,(actor.principal_id,path,r.text))
                self.assertNotIn("secret-a",r.text)
        self.current=self.a
        self.permissions=False
        self.assertEqual(self.client.get(f"/api/v1/conversations/{cid}").status_code,404)
        self.assertEqual(self.client.get(f"/api/v1/runs/{self.run_a}/events").status_code,404)

    def test_turn_cannot_attach_wrong_project_or_another_conversation_run(self):
        cid=self.conversation();turn=self.turn(cid)
        self.assertEqual(self.client.post(f"/api/v1/turns/{turn}/runs/{self.run_b}").status_code,404)
        self.client.post(f"/api/v1/turns/{turn}/runs/{self.run_a}")
        cid2=self.conversation();turn2=self.turn(cid2)
        self.assertEqual(self.client.post(f"/api/v1/turns/{turn2}/runs/{self.run_a}").status_code,409)
        # Headers never impersonate a trusted Gateway principal.
        self.current=None
        bad=self.client.post("/api/v1/conversations",json={"title":"forged"},
                             headers={"X-Principal-Id":"user-a","X-Project-Scope":"project-a"})
        self.assertEqual(bad.status_code,401)

    def test_sse_cursor_resume_and_live_authorization_isolation(self):
        url=f"/api/v1/runs/{self.run_a}/stream"
        first=self.client.get(url)
        self.assertEqual(first.status_code,200,first.text)
        self.assertIn("text/event-stream",first.headers["content-type"])
        self.assertIn("Hello from PG",first.text)
        self.assertIn("response.output_text.delta",first.text)
        events=self.db.events_since(self.run_a)
        cursor=events[-1]["seq"]
        replay=self.client.get(url,headers={"Last-Event-ID":f"{self.run_a}:{cursor}"})
        self.assertEqual(replay.status_code,200,replay.text)
        self.assertNotIn("Hello from PG",replay.text)
        for bad in ("other:1",f"{self.run_a}:-1","garbage",f"{self.run_a}:"+("9"*5000)):
            self.assertEqual(self.client.get(url,headers={"Last-Event-ID":bad}).status_code,422)
        self.permissions=False
        self.assertEqual(self.client.get(url).status_code,404)

    def test_policy_revoked_between_sse_batches_leaks_no_later_event(self):
        self.policy_calls.clear()
        reader=PgRunReader(PgFacts())
        orig=reader.events_since
        def revoke_after_first(rid,after,limit):
            events=orig(rid,after,limit)
            self.permissions=False
            return events
        reader.events_since=revoke_after_first
        client=TestClient(create_platform_app(
            resolve_context=lambda _:self.current,reader=reader,
            store=self.store,authorize=lambda *_:self.permissions,
            authorize_create=lambda *_:self.permissions,sse_max_polls=3))
        stream=client.get(f"/api/v1/runs/{self.run_a}/stream")
        self.assertEqual(stream.status_code,200,stream.text)
        self.assertEqual(stream.text.count("Hello from PG"),1)
        self.assertFalse(self.permissions)

    def test_authorized_cancel_is_request_only_never_forge_engine_ack(self):
        url=f"/api/v1/runs/{self.run_a}/cancel"
        self.current=self.b
        self.assertEqual(self.client.post(url).status_code,404)
        self.assertEqual(self.db.run_state(self.run_a),"RUNNING")
        self.current=self.a
        r=self.client.post(url)
        self.assertEqual(r.status_code,202,r.text)
        self.assertEqual(r.json()["state"],"CANCEL_REQUESTED")
        self.assertEqual(self.client.post(url).status_code,202)
        self.assertEqual(self.db.run_state(self.run_a),"CANCEL_REQUESTED")
        self.assertEqual(sum(e["type"]=="run.cancel.requested"
                             for e in self.db.events_since(self.run_a)),1)

    def test_artifact_reference_is_metadata_not_unapproved_storage_url(self):
        cid=self.conversation();tid=self.turn(cid)
        self.client.post(f"/api/v1/turns/{tid}/runs/{self.run_a}")
        artifact="artifact-"+uuid4().hex
        digest=hashlib.sha256(b"synthetic pdf").hexdigest()
        self.store.register_artifact(artifact,self.run_a,"oss://synthetic/evidence/1",
                                     digest,"application/pdf",13)
        res=self.client.get(f"/api/v1/runs/{self.run_a}/artifacts")
        self.assertEqual(res.status_code,200,res.text)
        self.assertEqual(res.json()["artifacts"][0]["artifact_id"],artifact)
        self.assertEqual(res.json()["artifacts"][0]["digest"],digest)
        self.assertNotIn("oss://",res.text) # not a downloadable or signed URL
        self.assertEqual(self.client.get(f"/api/v1/artifacts/{artifact}").status_code,200)
        self.current=self.b
        self.assertEqual(self.client.get(f"/api/v1/artifacts/{artifact}").status_code,404)

    def test_legacy_unversioned_run_route_also_denies_same_project_other_user(self):
        self.current=self.same
        for path in (f"/api/runs/{self.run_a}",f"/api/runs/{self.run_a}/events"):
            self.assertEqual(self.client.get(path).status_code,404)

    def test_scoped_readable_html_safe_escaping_and_no_inspector_fallback(self):
        cid=self.conversation();tid=self.turn(cid)
        self.client.post(f"/api/v1/turns/{tid}/runs/{self.run_a}")
        page=self.client.get(f"/ui/conversations/{cid}")
        self.assertEqual(page.status_code,200,page.text)
        self.assertIn("text/html",page.headers["content-type"])
        self.assertIn("textContent",page.text)
        self.assertIn("/api/v1/conversations/",page.text)
        self.assertNotIn("secret-a",page.text) # browser fetches scoped endpoints
        self.assertNotIn("X-Principal-Id",page.text)
        self.permissions=False
        self.assertEqual(self.client.get(f"/ui/conversations/{cid}").status_code,404)

if __name__=="__main__":
    unittest.main()