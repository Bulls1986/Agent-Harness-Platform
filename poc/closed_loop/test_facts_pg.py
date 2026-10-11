"""PostgreSQL-only HC-02 contract tests: no Hatchet/Agent SDK mocks used as E2E evidence."""
from __future__ import annotations
import os
import unittest
from uuid import uuid4

from poc.closed_loop.facts import PgFacts, UnsafeDispatch
from poc.runtime_spi.contract import TypedEvent


@unittest.skipUnless(os.getenv("HARNESS_POC_DATABASE_URL"),
                     "Requires actual Docker PostgreSQL HARNESS_POC_DATABASE_URL")
class PostgreSQLFactsTests(unittest.TestCase):
    def setUp(self):
        self.db = PgFacts()
        self.run_id = "facts-" + uuid4().hex
        self.command = self.db.create(self.run_id, prompt="用户的演示输入")

    def event(self, runtime, output):
        return [TypedEvent(self.run_id, 1, "run.started", runtime),
                TypedEvent(self.run_id, 2, "run.completed", runtime,
                           {"result": output})]

    def test_atomic_run_and_outbox(self):
        snapshot = self.db.snapshot(self.run_id)
        self.assertEqual(snapshot["state"], "CREATED")
        self.assertEqual(snapshot["outbox"], "PENDING")
        self.assertEqual(snapshot["input_prompt"], "用户的演示输入")
        self.assertIsNone(snapshot["result"])
        self.assertEqual(snapshot["steps"]["pydantic"]["input"], "用户的演示输入")
        self.assertIsNone(snapshot["steps"]["openai"]["input"])
        self.assertEqual(set(snapshot["steps"]), {"pydantic", "openai"})
        with self.assertRaises(Exception):
            self.db.create(self.run_id)
        self.assertEqual(self.db.snapshot(self.run_id)["outbox"], "PENDING")

    def test_unknown_ack_fail_closed(self):
        self.db.dispatch(self.command)
        self.db.unknown(self.command)
        self.assertEqual(self.db.snapshot(self.run_id)["outbox"], "BLOCKED_UNKNOWN")
        with self.assertRaises(UnsafeDispatch):
            self.db.dispatch(self.command)
        self.assertIsNone(self.db.snapshot(self.run_id)["provider_workflow_run_id"])

    def test_live_binding_freeze_and_verification_are_required(self):
        live_id = 'live-' + uuid4().hex
        command = self.db.create(live_id, prompt='业务需求',
                                 model_mode='live', model_id='gateway-model-v1')
        self.db.assert_model_binding(live_id, 'live', 'gateway-model-v1')
        with self.assertRaises(UnsafeDispatch):
            self.db.assert_model_binding(live_id, 'deterministic_local_model', None)
        with self.assertRaises(UnsafeDispatch):
            self.db.assert_model_binding(live_id, 'live', 'other-model')
        self.db.dispatch(command)
        self.db.bind(command, 'provider-' + live_id)
        self.db.start_step(live_id, 'pydantic', '业务需求')
        self.db.finish_step(live_id, 'pydantic', 'validated-draft',
                            [TypedEvent(live_id, 1, 'run.completed', 'pydantic', {'result':'validated-draft'})])
        self.db.start_step(live_id, 'openai', 'validated-draft')
        self.db.finish_step(live_id, 'openai', 'verified-report',
                            [TypedEvent(live_id, 1, 'run.completed', 'openai-agents', {'result':'verified-report'})])
        with self.assertRaises(UnsafeDispatch):
            self.db.complete(live_id)
        self.assertEqual(self.db.snapshot(live_id)['state'], 'RUNNING')
        output = self.db.complete(live_id, verified_outputs={'pydantic':'validated-draft','openai':'verified-report'})
        self.assertEqual(output['openai'],'verified-report')
        result = self.db.snapshot(live_id)['result']
        self.assertEqual(result['mode'],'live')
        self.assertEqual(result['model_id'],'gateway-model-v1')

    def test_verified_parent_gate_and_terminal_immutability(self):
        self.db.dispatch(self.command)
        self.db.bind(self.command, "provider-" + self.run_id)
        with self.assertRaises(UnsafeDispatch):
            self.db.start_step(self.run_id, "openai", "input")
        with self.assertRaises(UnsafeDispatch):
            self.db.complete(self.run_id)
        self.db.start_step(self.run_id, "pydantic", "用户的演示输入")
        self.db.finish_step(self.run_id, "pydantic", "pydantic-output",
                            self.event("pydantic", "pydantic-output"))
        self.assertEqual(self.db.start_step(self.run_id, "pydantic", "用户的演示输入"),
                         "pydantic-output")
        with self.assertRaises(UnsafeDispatch):
            self.db.start_step(self.run_id, "pydantic", "different-prompt")
        self.db.start_step(self.run_id, "openai", "pydantic-output")
        self.db.finish_step(self.run_id, "openai", "openai-output",
                            self.event("openai-agents", "openai-output"))
        outputs = self.db.complete(self.run_id)
        self.assertEqual(outputs, {"pydantic": "pydantic-output",
                                   "openai": "openai-output"})
        with self.assertRaises(UnsafeDispatch):
            self.db.complete(self.run_id)
        another_connection = PgFacts()
        snapshot = another_connection.snapshot(self.run_id)
        self.assertEqual(snapshot["state"], "COMPLETED")
        self.assertEqual(snapshot["steps"]["openai"]["input"], "pydantic-output")
        self.assertEqual(snapshot["result"]["final_output"], "openai-output")
        self.assertEqual(snapshot["result"]["result_source_step"], "openai")
        self.assertEqual(snapshot["result"]["mode"], "deterministic_local_model")
        self.assertEqual(snapshot["result"]["step_outputs"], outputs)
        self.assertEqual(snapshot["steps"]["pydantic"]["attempts"], 1)
        self.assertEqual(snapshot["steps"]["openai"]["attempts"], 1)
        self.assertEqual([e["seq"] for e in snapshot["events"]],
                         list(range(1, len(snapshot["events"]) + 1)))
        self.assertEqual(sum(e["type"] == "run.completed" for e in snapshot["events"]), 1)


if __name__ == "__main__":
    unittest.main()