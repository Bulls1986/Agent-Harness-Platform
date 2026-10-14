"""M6: real PostgreSQL safety-contract tests. Synthetic artifacts are NOT live SDK evidence."""
import os
import unittest
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor

from poc.recipe.gates import ArtifactRef, RecipeBlocked, RecipeGate
from poc.closed_loop.facts import PgFacts
from poc.closed_loop.tool_receipt import ToolReceiptJournal, EffectEvidence

@unittest.skipUnless(os.getenv("HARNESS_POC_DATABASE_URL"), "real PG required")
class TestRecipe(unittest.TestCase):
    def setUp(self):
        self.store = RecipeGate(os.environ["HARNESS_POC_DATABASE_URL"])
        self.run = "m6-" + uuid4().hex
        self.steps = [
            {"name": "plan", "runtime": "pydantic", "effect": "PURE"},
            {"name": "code", "runtime": "openai", "effect": "WRITE"},
            {"name": "verify", "runtime": "pydantic", "effect": "PURE"}]
        self.recipe = {"version": "synthetic-v1", "steps": self.steps}
        self.store.freeze(self.run, self.recipe, scope="project-synthetic",
                          principal="synthetic-owner")
        # Fake provider binding is PG contract fixture; not Hatchet live evidence.
        base = PgFacts(os.environ["HARNESS_POC_DATABASE_URL"])
        command = self.run + ":segment-0:create:v1"
        base.dispatch(command)
        base.bind(command, "synthetic-provider-" + self.run)

    def tearDown(self):
        # Never pollute the existing localhost Inspector with test-only Runs.
        with self.store.db.tx() as c:
            if c.execute("SELECT to_regclass('harness_tool_intent') IS NOT NULL").fetchone()[0]:
                c.execute("DELETE FROM harness_tool_intent WHERE run_id=%s", (self.run,))
            c.execute("DELETE FROM harness_recipe_input WHERE run_id=%s", (self.run,))
            c.execute("DELETE FROM harness_recipe_step_approval WHERE run_id=%s", (self.run,))
            c.execute("DELETE FROM harness_recipe_step_meta WHERE run_id=%s", (self.run,))
            c.execute("DELETE FROM harness_recipe_frozen WHERE run_id=%s", (self.run,))
            c.execute("DELETE FROM harness_step_attempt WHERE run_id=%s", (self.run,))
            c.execute("DELETE FROM harness_event WHERE run_id=%s", (self.run,))
            c.execute("DELETE FROM harness_outbox WHERE run_id=%s", (self.run,))
            c.execute("DELETE FROM harness_step WHERE run_id=%s", (self.run,))
            c.execute("DELETE FROM harness_run WHERE id=%s AND "
                      "initiator_principal_id='synthetic-owner'", (self.run,))

    def ref(self, name):
        return ArtifactRef("oss://synthetic/" + self.run + "/" + name,
                           "sha256:" + "a" * 64, "project-synthetic")

    def finish_plan(self):
        self.assertIsNone(self.store.claim_step(self.run, "plan", self.run + "-a0"))
        self.store.verify_step(self.run, "plan", self.run + "-a0", self.ref("plan"),
                               "verifier:plan")

    def approve_code(self):
        self.finish_plan()
        self.store.request_approval(self.run, "code", "requester", "sha256:"+"b"*64)
        self.store.decide_approval(self.run, "code", "reviewer", "APPROVED")
        return self.run + "-a1"

    def ledger(self, attempt, *, reconcile=True):
        journal = ToolReceiptJournal(self.store.db)
        execution = self.run + "-exec"
        journal.register_intent(self.run, 1, "code", attempt, execution,
                                "synthetic-worker", 1, "repo.write",
                                "synthetic-target", self.run + ":effect")
        journal.dispatch(execution, "synthetic-worker", 1)
        if reconcile:
            journal.reconcile(execution, lambda _: [EffectEvidence(
                "synthetic-ledger-ref-" + self.run, execution, "repo.write",
                "synthetic-target", self.run + ":effect")])
        return journal, execution

    def test_write_requires_confirmed_external_receipt(self):
        attempt = self.approve_code()
        self.store.claim_step(self.run, "code", attempt)
        with self.assertRaises(RecipeBlocked):
            self.store.verify_step(self.run, "code", attempt, self.ref("code"),
                                   "verifier:code")
        journal, execution = self.ledger(attempt, reconcile=False)
        journal.mark_unknown(execution, "LOST_ACK")
        with self.assertRaises(RecipeBlocked):
            self.store.verify_step(self.run, "code", attempt, self.ref("code"),
                                   "verifier:code")
        journal.reconcile(execution, lambda _: [EffectEvidence(
            "synthetic-ledger-ref-" + self.run, execution, "repo.write",
            "synthetic-target", self.run + ":effect")])
        self.store.verify_step(self.run, "code", attempt, self.ref("code"),
                               "verifier:code")

    def test_write_permit_respects_approval_and_attempt(self):
        self.finish_plan()
        self.store.request_approval(self.run, "code", "requester", "sha256:"+"b"*64)
        with self.assertRaises(RecipeBlocked):
            self.store.require_write_permit(self.run, "code", self.run+"-a1")
        self.store.decide_approval(self.run, "code", "reviewer", "APPROVED")
        self.store.claim_step(self.run, "code", self.run+"-a1")
        self.assertEqual(self.store.require_write_permit(
            self.run, "code", self.run+"-a1"), "APPROVED")
        with self.assertRaises(RecipeBlocked):
            self.store.require_write_permit(self.run, "code", self.run+"-late")

    def test_waiting_input_is_persistent_scope_checked_and_single_resolution(self):
        self.finish_plan()
        self.store.request_input(
            self.run, "m6-synthetic-requester", "sha256:" + "a"*64)
        after_restart=RecipeGate(os.environ["HARNESS_POC_DATABASE_URL"])
        self.assertEqual(after_restart.snapshot(self.run)["state"],"WAITING_INPUT")
        with self.assertRaises(RecipeBlocked):
            after_restart.claim_step(self.run,"code",self.run+"-a1")
        with self.assertRaises(RecipeBlocked):
            after_restart.request_approval(self.run,"code","requester",
                                           "sha256:"+"b"*64)
        with self.assertRaises(RecipeBlocked):
            after_restart.answer_input(
                self.run,"m6-synthetic-requester",self.ref("answer"),"verifier:input")
        with self.assertRaises(RecipeBlocked):
            after_restart.answer_input(
                self.run,"reviewer",
                ArtifactRef("oss://cross",self.ref("answer").digest,"other-scope"),
                "verifier:input")
        self.assertEqual(after_restart.snapshot(self.run)["state"],"WAITING_INPUT")
        after_restart.answer_input(
            self.run,"reviewer",self.ref("answer"),"verifier:input")
        state=after_restart.snapshot(self.run)
        self.assertEqual(state["state"],"RUNNING")
        self.assertEqual(state["inputs"][0]["response_ref"],self.ref("answer").ref)
        self.assertEqual(state["inputs"][0]["state"],"RESOLVED")
        with self.assertRaises(RecipeBlocked):
            after_restart.answer_input(
                self.run,"another",self.ref("answer"),"verifier:input")
        after_restart.request_approval(self.run,"code","requester",
                                       "sha256:"+"b"*64)

    def test_same_frozen_input_and_approval_retry_reuses_original_facts(self):
        self.finish_plan()
        digest="sha256:"+"a"*64
        self.store.request_input(self.run,"input-requester",digest)
        original=len(self.store.snapshot(self.run)["events"])
        self.store.request_input(self.run,"input-requester",digest)
        self.assertEqual(len(self.store.snapshot(self.run)["events"]),original)
        with self.assertRaises(RecipeBlocked):
            self.store.request_input(self.run,"different-requester",digest)
        self.store.answer_input(self.run,"different-actor",self.ref("answer"),
                                "verifier:input")
        original=len(self.store.snapshot(self.run)["events"])
        self.store.request_input(self.run,"input-requester",digest)
        self.assertEqual(len(self.store.snapshot(self.run)["events"]),original)
        self.store.request_approval(self.run,"code","approval-requester",digest)
        original=len(self.store.snapshot(self.run)["events"])
        self.store.request_approval(self.run,"code","approval-requester",digest)
        self.assertEqual(len(self.store.snapshot(self.run)["events"]),original)
        self.store.decide_approval(self.run,"code","reviewer","APPROVED")
        original=len(self.store.snapshot(self.run)["events"])
        self.store.request_approval(self.run,"code","approval-requester",digest)
        self.assertEqual(len(self.store.snapshot(self.run)["events"]),original)
        with self.assertRaises(RecipeBlocked):
            self.store.request_approval(self.run,"code","another",digest)

    def test_input_cannot_reopen_after_approval_or_running_code(self):
        self.finish_plan()
        self.store.request_approval(self.run,"code","requester",
                                    "sha256:"+"b"*64)
        with self.assertRaises(RecipeBlocked):
            self.store.request_input(
                self.run,"new-requester","sha256:"+"a"*64)
        self.store.decide_approval(self.run,"code","reviewer","APPROVED")
        self.store.claim_step(self.run,"code",self.run+"-a1")
        with self.assertRaises(RecipeBlocked):
            self.store.request_input(
                self.run,"new-requester","sha256:"+"a"*64)

    def test_verified_cross_runtime_handoff(self):
        self.finish_plan()
        with self.assertRaises(RecipeBlocked):
            self.store.claim_step(self.run, "code", self.run + "-a1")
        self.store.request_approval(self.run, "code", "requester", "sha256:" + "b"*64)
        with self.assertRaises(RecipeBlocked):
            self.store.claim_step(self.run, "code", self.run + "-a1")
        self.store.decide_approval(self.run, "code", "reviewer", "APPROVED")
        self.assertEqual(self.store.claim_step(self.run, "code", self.run + "-a1"), self.ref("plan"))
        self.ledger(self.run + "-a1")
        self.store.verify_step(self.run, "code", self.run + "-a1", self.ref("code"), "verifier:code")
        self.assertEqual(self.store.claim_step(self.run, "verify", self.run + "-a2"), self.ref("code"))
        self.store.verify_step(self.run, "verify", self.run + "-a2", self.ref("verified"), "verifier:final")
        state = self.store.snapshot(self.run)
        self.assertEqual(state["state"], "COMPLETED")
        self.assertEqual([x["state"] for x in state["steps"]], ["VERIFIED"]*3)
        self.assertEqual(state["steps"][1]["input_ref"], self.ref("plan").ref)
        self.assertEqual(len([x for x in state["events"] if x["type"] == "recipe.completed"]), 1)

    def test_unverified_foreign_artifact_and_evidence_fail_closed(self):
        with self.assertRaises(RecipeBlocked):
            self.store.claim_step(self.run, "code", self.run + "-a1")
        self.store.claim_step(self.run, "plan", self.run + "-a0")
        with self.assertRaises(RecipeBlocked):
            self.store.verify_step(self.run, "plan", self.run + "-a0",
                                   ArtifactRef("oss://other", "sha256:"+"a"*64, "other"),
                                   "verifier:plan")
        with self.assertRaises(RecipeBlocked):
            self.store.verify_step(self.run, "plan", self.run + "-a0", self.ref("plan"), "")
        self.assertEqual(self.store.snapshot(self.run)["steps"][0]["state"], "RUNNING")

    def test_approval_reject_wrong_actor_and_no_retry(self):
        self.finish_plan()
        self.store.request_approval(self.run, "code", "requester", "sha256:"+"b"*64)
        with self.assertRaises(RecipeBlocked):
            self.store.decide_approval(self.run, "code", "requester", "APPROVED")
        self.store.decide_approval(self.run, "code", "reviewer", "REJECTED")
        with self.assertRaises(RecipeBlocked):
            self.store.claim_step(self.run, "code", self.run + "-a1")
        with self.assertRaises(RecipeBlocked):
            self.store.decide_approval(self.run, "code", "another", "APPROVED")
        self.assertEqual(self.store.snapshot(self.run)["state"], "BLOCKED")

    def test_restart_after_write_dispatch_is_unknown_not_replayed(self):
        self.finish_plan()
        self.store.request_approval(self.run, "code", "requester", "sha256:"+"b"*64)
        self.store.decide_approval(self.run, "code", "reviewer", "APPROVED")
        self.store.claim_step(self.run, "code", self.run + "-a1")
        restarted = RecipeGate(os.environ["HARNESS_POC_DATABASE_URL"])
        for attempt in (self.run + "-a1", self.run + "-a1-new"):
            with self.assertRaises(RecipeBlocked):
                restarted.claim_step(self.run, "code", attempt)
        with self.assertRaises(RecipeBlocked):
            restarted.verify_step(self.run, "code", "wrong", self.ref("code"), "verifier:code")
        self.assertEqual(restarted.snapshot(self.run)["steps"][1]["state"], "RUNNING")

    def test_waiting_approval_survives_restart(self):
        self.finish_plan()
        self.store.request_approval(self.run, "code", "requester",
                                    "sha256:" + "b"*64)
        resumed = RecipeGate(os.environ["HARNESS_POC_DATABASE_URL"])
        self.assertEqual(resumed.snapshot(self.run)["state"], "WAITING_APPROVAL")
        with self.assertRaises(RecipeBlocked):
            resumed.claim_step(self.run, "code", self.run + "-a1")
        resumed.decide_approval(self.run, "code", "reviewer", "APPROVED")
        self.assertEqual(resumed.claim_step(self.run, "code", self.run + "-a1"),
                         self.ref("plan"))

    def test_concurrent_attempts_not_double_dispatched(self):
        def try_start(attempt):
            try:
                self.store.claim_step(self.run, "plan", self.run + "-" + attempt)
                return "claimed"
            except RecipeBlocked:
                return "blocked"
        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(try_start, ("a0", "a0-other")))
        self.assertCountEqual(result, ["claimed", "blocked"])
        snap = self.store.snapshot(self.run)
        self.assertEqual(snap["steps"][0]["state"], "RUNNING")

    def test_recipe_freeze_prevents_drift(self):
        self.assertEqual(self.store.freeze(self.run, self.recipe, scope="project-synthetic",
                                              principal="synthetic-owner"),
                         self.store.snapshot(self.run)["digest"])
        with self.assertRaises(RecipeBlocked):
            self.store.freeze(self.run, {**self.recipe, "version": "v2"},
                                  scope="project-synthetic", principal="synthetic-owner")
        with self.assertRaises(RecipeBlocked):
            self.store.freeze(self.run, self.recipe, scope="project-other",
                                  principal="synthetic-owner")

if __name__ == "__main__":
    unittest.main()