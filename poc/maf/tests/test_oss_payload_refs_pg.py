"""Real S3-compatible provider + PostgreSQL metadata/GC + Workspace restore."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import psycopg
try:
    import boto3
    from botocore.config import Config
except ImportError:  # optional requirements-oss.txt, not a core SDK dependency
    boto3 = None
    Config = None

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from oss_payload_refs import (
    PayloadIdentity,PayloadIntegrityError,PayloadRefStore,
)
from recovery_point_store import RecoveryPointRefs,RecoveryPointStore
from task_ledger import TaskFactConflict,TaskLedger
from workflow_probe import VerificationFact


@unittest.skipUnless(os.environ.get("POC_POSTGRES_DSN") and os.environ.get("POC_OSS_ENDPOINT") and boto3 is not None,
                     "optional boto3 and disposable PostgreSQL plus separate S3-compatible OSS required")
class RealObjectStorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn=os.environ["POC_POSTGRES_DSN"]
        cls.bucket=os.environ["POC_OSS_BUCKET"]
        cls.s3=boto3.client(
            "s3",endpoint_url=os.environ["POC_OSS_ENDPOINT"],
            aws_access_key_id="local-test-only",
            aws_secret_access_key="local-test-only",
            region_name="us-east-1",
            config=Config(s3={"addressing_style":"path"},retries={"max_attempts":1}),
        )
        cls.s3.create_bucket(Bucket=cls.bucket)
        cls.ledger=TaskLedger(cls.dsn)
        cls.ledger.initialize()
        cls.refs=RecoveryPointStore(cls.dsn)
        cls.payloads=PayloadRefStore(cls.dsn,s3=cls.s3,bucket=cls.bucket)

    def fixture(self,kind="ARTIFACT"):
        fact=VerificationFact.example(passed=False,evidence_ref=None)
        execution_id=self.ledger.start(fact)
        identity=PayloadIdentity(fact.run_id,fact.step_id,fact.attempt_id,
                                 execution_id,kind,"application/octet-stream",
                                 "retention:poc")
        return fact,identity

    def test_real_oss_digest_workspace_restore_pin_and_tombstone(self):
        fact,artifact=self.fixture()
        workspace=replace(artifact,kind="WORKSPACE",media_type="text/plain")
        evidence=replace(artifact,kind="EVIDENCE")
        source=b"workspace state from immutable external OSS\n"
        ws=self.payloads.put(workspace,source)
        ev=self.payloads.put(evidence,b"evidence report")
        ar=self.payloads.put(artifact,b"artifact report")
        self.assertEqual(self.payloads.get(ws.payload_id),source)
        self.assertEqual(self.payloads.get(ev.payload_id),b"evidence report")
        self.assertEqual(self.payloads.get(ar.payload_id),b"artifact report")

        rp=self.refs.record(RecoveryPointRefs(
            run_id=fact.run_id,step_id=fact.step_id,attempt_id=fact.attempt_id,
            runtime_type="maf",workspace_state_ref=ws.payload_id,
            environment_fingerprint="oss-test-frozen-environment",
        ))
        self.payloads.pin_to_recovery_point(ev.payload_id,rp)
        with tempfile.TemporaryDirectory(prefix="oss-restored-workspace-") as tmp:
            base=Path(tmp)
            dest=self.payloads.restore_workspace_file(
                ws.payload_id,base,"repo/module/doc.txt")
            self.assertEqual(dest.read_bytes(),source)
            with self.assertRaises(ValueError):
                self.payloads.restore_workspace_file(ws.payload_id,base,"../escape.txt")
        self.assertEqual(self.payloads.purge(ws.payload_id),"PINNED_RUN_RECOVERABLE")
        self.assertEqual(self.payloads.purge(ev.payload_id),"PINNED_RUN_RECOVERABLE")
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                "UPDATE poc_runs SET state='ABORTED',terminal_at=now() WHERE run_id=%s",
                (fact.run_id,),
            )
        self.assertEqual(self.payloads.purge(ws.payload_id),
                         "PURGED_TOMBSTONE_RETAINED")
        self.assertEqual(self.payloads.purge(ev.payload_id),
                         "PURGED_TOMBSTONE_RETAINED")
        self.assertEqual(self.payloads.purge(ar.payload_id),
                         "PURGED_TOMBSTONE_RETAINED")
        self.assertEqual(self.payloads.purge(ws.payload_id),"ALREADY_PURGED")
        meta=self.payloads.metadata(ws.payload_id)
        self.assertIsNone(meta["object_key"])
        self.assertIsNotNone(meta["purged_at"])
        self.assertEqual(meta["content_sha256"],ws.content_sha256)
        with self.assertRaises(PayloadIntegrityError):
            self.payloads.get(ws.payload_id)

    def test_real_object_digest_tampering_is_rejected_before_restore(self):
        _,identity=self.fixture(kind="WORKSPACE")
        ref=self.payloads.put(identity,b"trusted workspace")
        metadata=self.payloads.metadata(ref.payload_id)
        self.s3.put_object(
            Bucket=self.bucket,Key=metadata["object_key"],
            Body=b"attacker-overwritten-payload",
        )
        with self.assertRaises(PayloadIntegrityError):
            self.payloads.get(ref.payload_id)
        with tempfile.TemporaryDirectory(prefix="oss-tamper-") as tmp:
            target=Path(tmp)/"no-file.txt"
            with self.assertRaises(PayloadIntegrityError):
                self.payloads.restore_workspace_file(ref.payload_id,Path(tmp),
                                                     "no-file.txt")
            self.assertFalse(target.exists())

    def test_oss_pin_rejects_other_run_and_payload_reference_lineage(self):
        first,identity=self.fixture(kind="EVIDENCE")
        wrong_run,other=self.fixture(kind="WORKSPACE")
        ev=self.payloads.put(identity,b"authored test report")
        rp=self.refs.record(RecoveryPointRefs(
            run_id=wrong_run.run_id,step_id=wrong_run.step_id,
            attempt_id=wrong_run.attempt_id,
            runtime_type="maf",
            workspace_state_ref="externally-managed-workspace-ref",
            environment_fingerprint="frozen-env",
        ))
        with self.assertRaises(TaskFactConflict):
            self.payloads.pin_to_recovery_point(ev.payload_id,rp)
        with self.assertRaises(TaskFactConflict):
            self.payloads.put(replace(identity,run_id=wrong_run.run_id),b"forged")
