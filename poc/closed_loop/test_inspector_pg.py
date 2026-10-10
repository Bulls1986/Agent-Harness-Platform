"""Inspector contract tests against *real Docker PostgreSQL*; runner stub tests HTTP only.

End-to-end Hatchet/SDK proof is separately required, never replaced by stub.
"""
from __future__ import annotations
import os
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from poc.closed_loop.facts import PgFacts
from poc.closed_loop.inspector import create_app


@unittest.skipUnless(os.getenv("HARNESS_POC_DATABASE_URL"), "Docker PG required")
class InspectorAPIContractTests(unittest.TestCase):
    def setUp(self):
        self.started = []
        self.db = PgFacts()
        self.app = create_app(
            facts_factory=lambda: PgFacts(),
            submit=lambda run_id, prompt, command_key: self.started.append(
                (run_id, prompt, command_key)
            ),
        )
        self.client = TestClient(self.app)

    def test_start_and_refresh_are_real_pg_reads(self):
        response = self.client.post("/api/runs", json={"prompt": "inspect PG facts"})
        self.assertEqual(response.status_code, 202, response.text)
        obj = response.json()
        run_id = obj["run_id"]
        self.assertEqual(len(self.started), 1)
        self.assertEqual(self.started[0][0], run_id)
        self.assertEqual(self.started[0][1], "inspect PG facts")
        record = self.client.get(f"/api/runs/{run_id}")
        self.assertEqual(record.status_code, 200, record.text)
        snap = record.json()
        self.assertEqual(snap["state"], "CREATED")
        self.assertEqual(snap["outbox"], "PENDING")
        self.assertEqual(set(snap["steps"]), {"pydantic", "openai"})
        self.assertIn(run_id, [x["run_id"] for x in
                               self.client.get("/api/runs").json()["runs"]])
        after_0 = self.client.get(f"/api/runs/{run_id}/events?after=0")
        self.assertEqual(after_0.status_code, 200)
        self.assertEqual([x["seq"] for x in after_0.json()["events"]], [1])
        after_1 = self.client.get(f"/api/runs/{run_id}/events?after=1")
        self.assertEqual(after_1.json()["events"], [])
        self.assertEqual(PgFacts().snapshot(run_id)["state"], "CREATED")

    def test_missing_run_and_invalid_payload_rejected(self):
        bad = self.client.post("/api/runs", json={"prompt": "   "})
        self.assertEqual(bad.status_code, 422)
        self.assertEqual(len(self.started), 0)
        self.assertEqual(self.client.get("/api/runs/missing-" + uuid4().hex).status_code, 404)
        self.assertEqual(self.client.get("/api/runs/not-found/events").status_code, 404)
        self.assertEqual(self.client.get("/api/runs/not-found/events?after=-1").status_code, 422)

    def test_no_backend_does_not_fake_success(self):
        client = TestClient(create_app(facts_factory=lambda: PgFacts(), submit=None))
        response = client.post("/api/runs", json={"prompt": "cannot run"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(len(self.started), 0)

    def test_index_debug_only_and_text_safe(self):
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Run Inspector", page.text)
        self.assertIn("Local POC", page.text)
        self.assertIn("textContent", page.text)
        self.assertNotIn("innerHTML", page.text)


if __name__ == "__main__":
    unittest.main()