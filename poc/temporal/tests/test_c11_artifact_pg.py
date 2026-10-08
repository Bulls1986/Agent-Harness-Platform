"""C11 independent real-PG negative contracts; no cloud credentials required."""
from __future__ import annotations
import os
import sys
import unittest
from pathlib import Path
import psycopg

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from c11_facts import C11Facts,C11Run


@unittest.skipUnless(os.environ.get("POC_C_PLATFORM_DSN"),
                     "C11 requires actual Harness PostgreSQL")
class ArtifactEvidencePGTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts=C11Facts(os.environ["POC_C_PLATFORM_DSN"])
        cls.facts.initialize()

    def fixture(self):
        run=C11Run.build("sha256:"+"a"*64)
        self.facts.prepare(run)
        return run,run.request()

    def test_frozen_sandbox_providers_and_version_negatives(self):
        run,request=self.fixture()
        for st in request["stages"]:
            self.facts.frozen(request,st)
        for key in ("native_workflow_id","frozen_image_digest","frozen_workflow_version"):
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.facts.frozen(request|{key:"tampered"},request["stages"][0])
        bad=request["stages"][0]|{"provider":"docker-session"}
        with self.assertRaises(ValueError):
            self.facts.frozen(request,bad)
        with psycopg.connect(self.facts.dsn) as pg:
            with self.assertRaises(psycopg.Error):
                pg.execute("UPDATE poc_c11_sandbox_stages SET provider='docker-session' "
                           "WHERE attempt_id=%s",(run.stages[0]["attempt_id"],))
        with psycopg.connect(self.facts.dsn) as pg:
            with self.assertRaises(psycopg.Error):
                pg.execute("DELETE FROM poc_c11_runs WHERE run_id=%s",(run.run_id,))

    def test_invalid_artifact_lineage_and_immutable_digest(self):
        run,request=self.fixture()
        s=run.stages[0]
        with psycopg.connect(self.facts.dsn) as pg:
            with self.assertRaises(psycopg.Error):
                pg.execute("""INSERT INTO poc_c11_payload_metadata
                  (payload_id,run_id,step_id,attempt_id,execution_id,kind,media_type,
                   sha256_hex,size_bytes,storage_ref)
                  VALUES('forged',%s,'wrong-step',%s,%s,'ARTIFACT',
                         'application/octet-stream',%s,262160,'s3://poc/test')""",
                  (run.run_id,s["attempt_id"],s["execution_id"],"a"*64))
        valid=self.facts.record_artifact(request,s,"b"*64,262160,
                                         "s3://poc-c11-artifacts/mock-valid")
        with psycopg.connect(self.facts.dsn) as pg:
            with self.assertRaises(psycopg.Error):
                pg.execute("UPDATE poc_c11_payload_metadata SET sha256_hex=%s "
                           "WHERE payload_id=%s",("f"*64,valid))
        self.assertEqual(self.facts.artifact(request,s)["payload_id"],valid)

    def test_recoverable_run_pin_blocks_gc_and_payload_metadata_delete(self):
        run,request=self.fixture()
        s=run.stages[0]
        pid=self.facts.record_artifact(
            request,s,"e"*64,262160,"s3://poc-c11-artifacts/mock-pin")
        with self.assertRaises(psycopg.Error):
            self.facts.release_pin(pid)
        with self.assertRaises(psycopg.Error):
            self.facts.purge(pid)
        with psycopg.connect(self.facts.dsn) as pg:
            with self.assertRaises(psycopg.Error):
                pg.execute("DELETE FROM poc_c11_payload_metadata WHERE payload_id=%s",
                           (pid,))
        still=self.facts.artifact(request,s)
        self.assertEqual(still["payload_status"],"AVAILABLE")

    def test_purge_after_explicit_release_retains_tombstone_and_lineage(self):
        run,request=self.fixture()
        s=run.stages[0]
        pid=self.facts.record_artifact(request,s,"c"*64,262160,
                                       "s3://poc-c11-artifacts/mock-purge")
        # Fake terminal transition is PG contract test setup only; the real
        # C11 Workflow must reach terminal state through C11Facts.complete.
        with psycopg.connect(self.facts.dsn) as pg:
            pg.execute("UPDATE poc_runs SET state='COMPLETED',terminal_at=now() "
                       "WHERE run_id=%s",(run.run_id,))
        with self.assertRaises(psycopg.Error):
            self.facts.purge(pid)
        self.facts.release_pin(pid)
        self.facts.purge(pid)
        row=next(x for x in self.facts.rows(run.run_id) if x["payload_id"]==pid)
        self.assertEqual(row["payload_status"],"PURGED")
        self.assertEqual(row["sha256_hex"],"c"*64)
        self.assertEqual(row["attempt_id"],s["attempt_id"])
        self.assertIsNone(row["storage_ref"])
        self.assertIsNotNone(row["purged_at"])
        with psycopg.connect(self.facts.dsn) as pg:
            with self.assertRaises(psycopg.Error):
                pg.execute("UPDATE poc_c11_payload_metadata SET payload_status='AVAILABLE' "
                           "WHERE payload_id=%s",(pid,))


if __name__=="__main__":
    unittest.main()
