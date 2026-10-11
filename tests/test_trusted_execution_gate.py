"""DEV-M5 contract: untrusted workflow payload must not grant Cube/Tool authority."""
from dataclasses import replace
import unittest

from poc.runtime_spi.trusted_gate import (
    ExecutionClaim, ExecutionRecord, SandboxRecord, TrustedExecutionGate, GateDenied,
)

class BindingGateTests(unittest.TestCase):
    def setUp(self):
        self.now=20000.0
        self.record=ExecutionRecord(
            run_id="run",step_id="step",attempt_id="attempt",execution_id="exec",
            plan_version=1,provider_binding_ref="hatchet:workflow",
            principal_ref="principal:1",isolation_scope="project:alpha",
            workspace_ref="workspace:revision",runtime_adapter_version="pydantic:1",
            environment_digest="sha256:env",owner_id="worker:new",fencing_epoch=3,
            lease_expires_at=self.now+60,capabilities=frozenset({"model.run","files.read","shell.exec"}),
        )
        self.claim=ExecutionClaim.from_record(self.record)
        self.sandbox=SandboxRecord(
            sandbox_id="cube:opaque",isolation_scope=self.record.isolation_scope,
            workspace_ref=self.record.workspace_ref,environment_digest=self.record.environment_digest,
            binding_generation=4,owner_id=self.record.owner_id,fencing_epoch=self.record.fencing_epoch,
        )
        self.gate=TrustedExecutionGate()

    def test_model_only_does_not_allocate_sandbox(self):
        result=self.gate.authorize(self.claim,self.record,"model.run",now=self.now)
        self.assertIsNone(result.sandbox_ref)
        self.assertEqual(result.execution_id,"exec")

    def test_files_requires_verified_sandbox(self):
        with self.assertRaises(GateDenied):
            self.gate.authorize(self.claim,self.record,"files.read",now=self.now)
        approved=self.gate.authorize(self.claim,self.record,"files.read",now=self.now,
                                     sandbox=self.sandbox)
        self.assertEqual(approved.sandbox_ref,"cube:opaque")

    def test_stale_fencing_owner_and_expiry_are_rejected(self):
        for changes in ({"fencing_epoch":2},{"owner_id":"worker:old"},
                        {"lease_expires_at":self.now-1}):
            with self.subTest(changes=changes),self.assertRaises(GateDenied):
                self.gate.authorize(self.claim,replace(self.record,**changes),
                                    "model.run",now=self.now)
        with self.assertRaises(GateDenied):
            self.gate.authorize(self.claim,self.record,"model.run",now=self.now+60)

    def test_cross_scope_and_frozen_identity_rejected(self):
        for changes in ({"isolation_scope":"project:other"},{"plan_version":2},
                        {"runtime_adapter_version":"pydantic:latest"},
                        {"principal_ref":"other"},{"workspace_ref":"workspace:changed"},
                        {"environment_digest":"sha256:other"},{"execution_id":"x"}):
            with self.subTest(changes=changes),self.assertRaises(GateDenied):
                self.gate.authorize(replace(self.claim,**changes),
                                    self.record,"model.run",now=self.now)

    def test_capability_cannot_be_inferred_from_sandbox_id(self):
        with self.assertRaises(GateDenied):
            self.gate.authorize(self.claim,self.record,"git.push",now=self.now,sandbox=self.sandbox)
        for changes in ({"isolation_scope":"project:other"},{"fencing_epoch":2},
                        {"workspace_ref":"workspace:other"},{"binding_generation":0}):
            with self.subTest(changes=changes),self.assertRaises(GateDenied):
                self.gate.authorize(self.claim,self.record,"shell.exec",now=self.now,
                                    sandbox=replace(self.sandbox,**changes))

    def test_missing_authority_is_fail_closed(self):
        with self.assertRaises(GateDenied):
            self.gate.authorize(self.claim,None,"model.run",now=self.now)

if __name__=="__main__": unittest.main()
