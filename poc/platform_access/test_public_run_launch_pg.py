"""DEV-M7 original: versioned public API -> trusted Harness Run create/dispatch.

Real PostgreSQL is compulsory. Native Hatchet execution acceptance is in
verify_public_api_hatchet.py; no mock engine passes that gate.
"""
from __future__ import annotations
import os
import unittest
from uuid import uuid4
from fastapi.testclient import TestClient
from poc.closed_loop.facts import PgFacts
from poc.platform_access.authorized_reads import SecurityContext
from poc.platform_access.pg_reader import PgRunReader
from poc.platform_access.conversation_pg import PgConversationStore
from poc.platform_access.platform_api import create_platform_app


@unittest.skipUnless(os.getenv("HARNESS_POC_DATABASE_URL"),"Actual PostgreSQL required")
class PublicRunLaunchPgTests(unittest.TestCase):
    def setUp(self):
        self.facts=PgFacts()
        self.store=PgConversationStore(self.facts)
        self.ctx=SecurityContext("alice","USER","project-alpha")
        self.allowed=True
        self.started=[]
        def submit(rid,prompt,key):
            self.started.append((rid,prompt,key))
        self.client=TestClient(create_platform_app(
            resolve_context=lambda _:self.ctx,
            reader=PgRunReader(PgFacts()),store=self.store,
            authorize=lambda *_:self.allowed,authorize_create=lambda *_:self.allowed,
            start_run=submit,model_binding=lambda:("deterministic_local_model",None),
            admit_recipe=lambda agent,recipe: (agent,recipe)==("pydantic-ai@v1","review@v1"),
            sse_max_polls=1,
        ))
        cid=self.client.post("/api/v1/conversations",json={"title":"synthetic design"}).json()["conversation_id"]
        tid=self.client.post(f"/api/v1/conversations/{cid}/turns",json={
            "message":"Analyze a synthetic product brief","agent_ref":"pydantic-ai@v1",
            "recipe_ref":"review@v1"}).json()["turn_id"]
        self.tid=tid
        self.url=f"/api/v1/turns/{tid}/runs"
        self.h={"Idempotency-Key":"request-"+uuid4().hex}

    def test_creates_persisted_scoped_run_before_one_dispatch(self):
        r=self.client.post(self.url,headers=self.h)
        self.assertEqual(r.status_code,202,r.text)
        body=r.json()
        self.assertEqual(body["state"],"CREATED")
        self.assertFalse(body["replayed"])
        rid=body["run_id"]
        self.assertEqual(self.started,[(rid,"Analyze a synthetic product brief",rid+":segment-0:create:v1")])
        binding=PgRunReader(PgFacts()).binding(rid)
        self.assertEqual((binding.project_scope,binding.initiator_principal_id),
                         ("project-alpha","alice"))
        snap=PgFacts().snapshot(rid)
        self.assertEqual(snap["outbox"],"PENDING")
        self.assertEqual(snap["state"],"CREATED")
        self.assertEqual(self.client.get(f"/api/v1/runs/{rid}").status_code,200)
        conv=self.store.conversation(self.store.turn_binding(self.tid)["conversation_id"])
        self.assertEqual(conv["turns"][0]["run_ids"],[rid])

    def test_retry_same_key_does_not_dispatch_a_second_workflow(self):
        first=self.client.post(self.url,headers=self.h)
        second=self.client.post(self.url,headers=self.h)
        self.assertEqual(first.status_code,202,first.text)
        self.assertEqual(second.status_code,202,second.text)
        self.assertEqual(first.json()["run_id"],second.json()["run_id"])
        self.assertTrue(second.json()["replayed"])
        self.assertEqual(len(self.started),1)
        self.assertEqual(len(self.store.conversation(
            self.store.turn_binding(self.tid)["conversation_id"])["turns"][0]["run_ids"]),1)

    def test_two_keys_create_two_distinct_runs_under_one_turn(self):
        one=self.client.post(self.url,headers=self.h).json()["run_id"]
        two=self.client.post(self.url,headers={"Idempotency-Key":"other-"+uuid4().hex}).json()["run_id"]
        self.assertNotEqual(one,two)
        self.assertEqual(len(self.started),2)

    def test_rejected_identity_policy_or_bad_key_never_creates_run(self):
        self.ctx=None
        self.assertEqual(self.client.post(self.url,headers=self.h).status_code,401)
        self.ctx=SecurityContext("mallory","USER","project-alpha")
        self.assertEqual(self.client.post(self.url,headers=self.h).status_code,404)
        self.ctx=SecurityContext("alice","USER","other-project")
        self.assertEqual(self.client.post(self.url,headers=self.h).status_code,404)
        self.ctx=SecurityContext("alice","USER","project-alpha")
        self.allowed=False
        self.assertEqual(self.client.post(self.url,headers=self.h).status_code,404)
        self.allowed=True
        self.assertEqual(self.client.post(self.url).status_code,422)
        self.assertEqual(self.client.post(self.url,headers={"Idempotency-Key":"\n"}).status_code,422)
        self.assertEqual(self.started,[])

    def test_unsupported_agent_recipe_ref_cannot_dispatch(self):
        untrusted=self.client.post(
            "/api/v1/conversations",json={"title":"unknown"}
        ).json()["conversation_id"]
        turn=self.client.post(f"/api/v1/conversations/{untrusted}/turns",json={
            "message":"hello","agent_ref":"unsupported-agent@99",
            "recipe_ref":"unsupported-recipe@99",
        }).json()["turn_id"]
        self.assertEqual(self.client.post(
            f"/api/v1/turns/{turn}/runs",headers=self.h
        ).status_code,404)
        self.assertEqual(self.started,[])

    def test_unavailable_execution_adapter_fails_before_run_allocation(self):
        app=create_platform_app(
            resolve_context=lambda _:self.ctx,reader=PgRunReader(PgFacts()),
            store=self.store,authorize=lambda *_:True,authorize_create=lambda *_:True)
        result=TestClient(app).post(self.url,headers=self.h)
        self.assertEqual(result.status_code,503,result.text)
        self.assertEqual(self.started,[])

    def test_submission_error_returns_persisted_run_id_without_retrying(self):
        failed=[]
        def timeout(rid,prompt,key):
            failed.append(rid)
            raise TimeoutError("Hatchet create ACK may be lost")
        app=create_platform_app(
            resolve_context=lambda _:self.ctx,reader=PgRunReader(PgFacts()),
            store=self.store,authorize=lambda *_:True,authorize_create=lambda *_:True,
            start_run=timeout,model_binding=lambda:("deterministic_local_model",None),
            admit_recipe=lambda *_:True)
        client=TestClient(app)
        first=client.post(self.url,headers=self.h)
        self.assertEqual(first.status_code,503,first.text)
        rid=first.json()["detail"]["run_id"]
        self.assertEqual(PgFacts().snapshot(rid)["state"],"CREATED")
        self.assertEqual(PgFacts().snapshot(rid)["outbox"],"PENDING")
        second=client.post(self.url,headers=self.h)
        self.assertEqual(second.status_code,202,second.text)
        self.assertTrue(second.json()["replayed"])
        self.assertTrue(second.json()["needs_reconciliation"])
        self.assertEqual(failed,[rid])

if __name__=="__main__":
    unittest.main()
