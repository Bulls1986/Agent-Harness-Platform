"""DEV-M7 real PostgreSQL Run ownership integration (no synthetic in-memory Reader).

Set HARNESS_POC_DATABASE_URL to a disposable PostgreSQL 16 test database.
This module is a real PG gate; never count a SKIP as success in its CI job.
"""
from __future__ import annotations

import os
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from poc.closed_loop.facts import PgFacts
from poc.platform_access.authorized_reads import SecurityContext, create_read_app
from poc.platform_access.pg_reader import PgRunReader


@unittest.skipUnless(os.getenv("HARNESS_POC_DATABASE_URL"),
                     "Requires actual PostgreSQL HARNESS_POC_DATABASE_URL")
class PostgresAuthorizedRunTests(unittest.TestCase):
    def setUp(self):
        self.db = PgFacts()
        self.run_a = "m7-pg-" + uuid4().hex
        self.run_b = "m7-pg-" + uuid4().hex
        self.legacy = "m7-old-" + uuid4().hex
        self.db.create(self.run_a, prompt="private A",
                       project_scope="project-A", initiator_principal_id="user-A")
        self.db.create(self.run_b, prompt="private B",
                       project_scope="project-B", initiator_principal_id="user-B")
        self.db.create(self.legacy, prompt="legacy unscoped")
        self.current = SecurityContext("user-A", "USER", "project-A")
        self.can_read = True
        self.client = TestClient(create_read_app(
            resolve_context=lambda _req: self.current,
            reader=PgRunReader(PgFacts()),
            authorize=lambda _ctx, _binding, _action: self.can_read,
        ))

    def test_persisted_binding_survives_new_connection_and_event_cursor(self):
        binding = PgRunReader(PgFacts()).binding(self.run_a)
        self.assertEqual((binding.run_id, binding.project_scope, binding.initiator_principal_id),
                         (self.run_a, "project-A", "user-A"))
        response = self.client.get("/api/runs/" + self.run_a)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["input_prompt"], "private A")
        events = self.client.get("/api/runs/" + self.run_a + "/events?after=0&limit=1")
        self.assertEqual(events.status_code, 200, events.text)
        self.assertEqual(events.json()["events"][0]["type"], "run.created")
        self.assertEqual(events.json()["cursor"], 1)
        empty = self.client.get("/api/runs/" + self.run_a + "/events?after=1&limit=1")
        self.assertEqual(empty.json()["events"], [])
        self.assertEqual(empty.json()["cursor"], 1)

    def test_other_project_and_legacy_run_hide_payload_even_with_headers(self):
        for rid in (self.run_b, self.legacy):
            for suffix in ("", "/events"):
                r = self.client.get("/api/runs/" + rid + suffix, headers={
                    "X-Principal-Id": "user-B", "X-Project-Scope": "project-B",
                })
                self.assertEqual(r.status_code, 404)
                self.assertNotIn("private", r.text)
        self.assertEqual(self.client.get("/api/runs/absent").status_code, 404)
        with self.assertRaises(KeyError):
            PgRunReader(self.db).binding(self.legacy)

    def test_revoked_policy_and_missing_identity_fail_closed(self):
        self.can_read = False
        self.assertEqual(self.client.get("/api/runs/" + self.run_a).status_code, 404)
        self.assertEqual(self.client.get("/api/runs/" + self.run_a + "/events").status_code, 404)
        self.can_read = True
        self.current = None
        self.assertEqual(self.client.get("/api/runs/" + self.run_a).status_code, 401)

    def test_postgres_rejects_in_place_owner_reassignment(self):
        # HTTP auth reads binding before payload. DB-level immutable owner
        # facts prevent another connection swapping the scope between reads.
        with self.assertRaises(Exception):
            with self.db.tx() as c:
                c.execute("UPDATE harness_run SET project_scope=%s WHERE id=%s",
                          ("project-C", self.run_a))
        with self.assertRaises(Exception):
            with self.db.tx() as c:
                c.execute("UPDATE harness_run SET project_scope=%s,"
                          "initiator_principal_id=%s WHERE id=%s",
                          ("project-A", "user-A", self.legacy))
        binding = PgRunReader(PgFacts()).binding(self.run_a)
        self.assertEqual(binding.project_scope, "project-A")
        with self.assertRaises(KeyError):
            PgRunReader(self.db).binding(self.legacy)

    def test_owner_fact_is_insert_only_and_scoping_must_be_complete(self):
        self.db.dispatch(self.run_a + ":segment-0:create:v1")
        bound = PgRunReader(PgFacts()).binding(self.run_a)
        self.assertEqual((bound.project_scope, bound.initiator_principal_id),
                         ("project-A", "user-A"))
        for kw in ({"project_scope": "project-A"},
                   {"initiator_principal_id": "user-A"},
                   {"project_scope": "", "initiator_principal_id": "user-A"}):
            with self.assertRaises(ValueError):
                self.db.create("m7-bad-" + uuid4().hex, prompt="reject", **kw)


if __name__ == "__main__":
    unittest.main()
