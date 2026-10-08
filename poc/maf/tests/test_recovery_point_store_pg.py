"""G2/G6 RecoveryPoint opaque reference lineage and safe capability choice."""
from __future__ import annotations

import os
import sys
import unittest
from dataclasses import replace
from pathlib import Path

import psycopg
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from recovery_point_store import RecoveryPointRefs, RecoveryPointStore
from task_ledger import TaskFactConflict,TaskLedger
from workflow_probe import VerificationFact


@unittest.skipUnless(os.environ.get("POC_POSTGRES_DSN"),"real PG required")
class RecoveryPointPGTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn=os.environ["POC_POSTGRES_DSN"]
        cls.ledger=TaskLedger(cls.dsn)
        cls.ledger.initialize()
        cls.points=RecoveryPointStore(cls.dsn)

    def fixture(self):
        fact=VerificationFact.example(passed=False,evidence_ref=None)
        self.ledger.start(fact)
        refs=RecoveryPointRefs(
            run_id=fact.run_id,step_id=fact.step_id,
            attempt_id=fact.attempt_id,runtime_type="maf",
            runtime_checkpoint_ref="opaque-maf-provider:checkpoint/v3",
            workspace_state_ref="workspace-state-ref:123",
            repository_revision_set={"repoA":"abc123","repoB":"def789"},
            environment_fingerprint="runtime-env-v1",
            sandbox_snapshot_ref="sandbox-snapshot-ref:optional",
            provider_fingerprint="maf-public-v1",
        )
        return fact,refs

    def choose(self,refs,**overrides):
        kw=dict(run_id=refs.run_id,attempt_id=refs.attempt_id,
                runtime_type=refs.runtime_type,
                provider_fingerprint=refs.provider_fingerprint,
                environment_fingerprint=refs.environment_fingerprint,
                checkpoint_capable=True,workspace_capable=True)
        kw.update(overrides)
        return self.points.choose(**kw)

    def test_references_persisted_immutably_without_runtime_payload(self):
        _,refs=self.fixture()
        first=self.points.record(refs)
        chosen=self.choose(refs)
        self.assertEqual(chosen.outcome,"CANDIDATE_REQUIRES_PROVIDER_VERIFICATION")
        self.assertEqual(chosen.recovery_point_id,first)
        self.assertEqual(chosen.runtime_checkpoint_ref,refs.runtime_checkpoint_ref)
        with psycopg.connect(self.dsn) as conn:
            row=conn.execute(
                """SELECT repository_revision_set,environment_fingerprint,
                          runtime_checkpoint_ref,sandbox_snapshot_ref
                   FROM poc_recovery_points WHERE recovery_point_id=%s""",
                (first,)).fetchone()
        self.assertEqual(row[0],dict(refs.repository_revision_set))
        self.assertEqual(row[1],refs.environment_fingerprint)
        self.assertEqual(row[2],refs.runtime_checkpoint_ref)
        self.assertEqual(row[3],refs.sandbox_snapshot_ref)
        with psycopg.connect(self.dsn) as conn:
            with self.assertRaises(psycopg.Error):
                conn.execute(
                    """UPDATE poc_recovery_points SET runtime_checkpoint_ref='rewritten'
                       WHERE recovery_point_id=%s""",(first,))
        # A newer immutable RecoveryPoint may supersede a previous one.
        second=self.points.record(replace(refs,runtime_checkpoint_ref="opaque:v4"))
        self.assertNotEqual(first,second)
        # Selection is explicitly a candidate: Runtime still must verify.
        self.assertEqual(self.choose(refs).runtime_checkpoint_ref,"opaque:v4")

    def test_frozen_identity_and_workspace_sandbox_preconditions(self):
        _,refs=self.fixture()
        second_fact,_=self.fixture()
        with self.assertRaises(TaskFactConflict):
            self.points.record(replace(refs,run_id=second_fact.run_id))
        with self.assertRaises(TaskFactConflict):
            self.points.record(replace(refs,runtime_type="temporal"))
        with self.assertRaises(TaskFactConflict):
            self.points.record(replace(refs,attempt_id=second_fact.attempt_id))
        with self.assertRaises(TaskFactConflict):
            self.points.record(replace(refs,workspace_state_ref=None))
        with self.assertRaises(ValueError):
            self.points.record(replace(refs,runtime_checkpoint_ref=None,
                                       workspace_state_ref=None,sandbox_snapshot_ref=None))
        with self.assertRaises(ValueError):
            self.points.record(replace(refs,environment_fingerprint=None))
        with self.assertRaises(ValueError):
            self.points.record(replace(refs,provider_fingerprint=None))

    def test_missing_capability_or_version_never_implicitly_resumes(self):
        _,refs=self.fixture()
        self.assertEqual(self.choose(refs).outcome,"RECOVERY_POINT_UNAVAILABLE")
        self.points.record(refs)
        self.assertEqual(self.choose(refs,checkpoint_capable=False).outcome,
                         "RECOVERY_UNSUPPORTED_RUNTIME")
        self.assertEqual(self.choose(refs,workspace_capable=False).outcome,
                         "RECOVERY_UNSUPPORTED_WORKSPACE")
        for override in ({"runtime_type":"temporal"},
                         {"provider_fingerprint":"upgraded-sdk"},
                         {"environment_fingerprint":"changed-container"}):
            with self.subTest(override=override):
                self.assertEqual(self.choose(refs,**override).outcome,
                                 "RECOVERY_INCOMPATIBLE")

    def test_workspace_only_reference_is_not_same_attempt_resume(self):
        _,refs=self.fixture()
        workspace=replace(refs,runtime_checkpoint_ref=None,sandbox_snapshot_ref=None)
        self.points.record(workspace)
        self.assertEqual(self.choose(workspace).outcome,
                         "STEP_BOUNDARY_REQUIRES_SEPARATE_DECISION")
        self.assertEqual(self.choose(workspace,workspace_capable=False).outcome,
                         "RECOVERY_UNSUPPORTED_WORKSPACE")


if __name__=="__main__":
    unittest.main()
