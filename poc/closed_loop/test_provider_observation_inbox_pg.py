"""DEV-M4 HC-02: real PostgreSQL Provider observation Inbox contract tests."""
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from poc.closed_loop.facts import PgFacts, UnsafeDispatch
from poc.closed_loop.provider_observation_inbox import ProviderObservationInbox, Observation


@unittest.skipUnless(os.getenv("HARNESS_POC_DATABASE_URL"), "Real PostgreSQL required")
class ProviderObservationInboxPgTests(unittest.TestCase):
    def setUp(self):
        self.db = PgFacts()
        self.rid = "m4-inbox-" + uuid4().hex
        command = self.db.create(self.rid, prompt="synthetic Native Task")
        self.db.dispatch(command)
        self.provider = "provider-" + self.rid
        self.db.bind(command, self.provider)
        self.inbox = ProviderObservationInbox(self.db)

    def obs(self, key="native-event-1", seq=1, state="SUCCEEDED",
            provider=None, digest="sha256:synthetic-result"):
        return Observation(
            run_id=self.rid, plan_version=1,
            provider_workflow_id=provider or self.provider,
            provider_task_ref="native-task-a", native_event_key=key,
            source_sequence=seq, provider_state=state,
            result_digest=digest)

    def rows(self):
        with self.db.tx() as c:
            return c.execute(
                "SELECT native_event_key,source_sequence,provider_state "
                "FROM harness_provider_observation_inbox WHERE run_id=%s",
                (self.rid,),
            ).fetchall()

    def event_count(self):
        return sum(e["type"] == "provider.observed"
                   for e in self.db.snapshot(self.rid)["events"])

    def test_duplicate_native_event_from_another_process_never_projects_twice(self):
        self.assertEqual(self.inbox.observe(self.obs()), "APPLIED")
        self.assertEqual(ProviderObservationInbox(PgFacts()).observe(self.obs()),
                         "ALREADY_APPLIED")
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(self.event_count(), 1)

    def test_duplicate_native_event_with_mutated_payload_is_rejected(self):
        self.inbox.observe(self.obs())
        with self.assertRaises(UnsafeDispatch):
            self.inbox.observe(self.obs(state="FAILED"))
        with self.assertRaises(UnsafeDispatch):
            self.inbox.observe(self.obs(digest="different"))
        self.assertEqual(self.event_count(), 1)

    def test_delayed_lower_sequence_and_conflicting_sequence_cannot_project(self):
        self.inbox.observe(self.obs(key="native-2", seq=2))
        for other in (self.obs(key="native-1",seq=1),
                      self.obs(key="different-key",seq=2)):
            with self.assertRaises(UnsafeDispatch):
                self.inbox.observe(other)
        self.assertEqual(self.event_count(), 1)

    def test_stale_provider_and_missing_binding_fail_closed(self):
        with self.assertRaises(UnsafeDispatch):
            self.inbox.observe(self.obs(provider="wrong-provider"))
        with self.assertRaises(UnsafeDispatch):
            self.inbox.observe(Observation(
                self.rid,2,self.provider,"task","event",1,"SUCCEEDED","sha256:test"))
        self.assertEqual(self.rows(), [])

    def test_concurrent_duplicate_observation_has_one_durable_projection(self):
        observation=self.obs()
        def apply(_):
            return ProviderObservationInbox(PgFacts()).observe(observation)
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(apply,range(2)))
        self.assertCountEqual(outcomes,["APPLIED","ALREADY_APPLIED"])
        self.assertEqual(self.event_count(),1)
        self.assertEqual(len(self.rows()),1)

    def test_native_success_is_not_business_completed_and_terminal_rejects_new(self):
        self.inbox.observe(self.obs())
        self.assertEqual(self.db.snapshot(self.rid)["state"], "RUNNING")
        self.db.request_cancel(self.rid)
        self.db.acknowledge_cancel(self.rid)
        before=self.db.snapshot(self.rid)["events"]
        with self.assertRaises(UnsafeDispatch):
            self.inbox.observe(self.obs(key="native-event-after-terminal",seq=2))
        self.assertEqual(self.inbox.observe(self.obs()),"ALREADY_APPLIED")
        self.assertEqual(self.db.snapshot(self.rid)["events"],before)

if __name__=="__main__":
    unittest.main()