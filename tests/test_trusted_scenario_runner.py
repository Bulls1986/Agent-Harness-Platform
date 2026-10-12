"""DEV-M5 B.3: authenticated, fail-closed Inspector scenario API (synthetic).

Fake command outputs are never treated as a real Cube/OS test. The separate
real-world B03 proof is required to accept a genuine new live execution.
"""
from __future__ import annotations

from pathlib import Path
import tempfile
import time
import unittest
from fastapi.testclient import TestClient

from poc.closed_loop.inspector import create_app
from poc.closed_loop.trusted_scenario_runner import TrustedScenarioRunner

TOKEN = "synthetic-test-operator-secret-" + "a" * 40
PROOF = {
    "outcome": "PASS_PHYSICAL_HATCHET_CUBE_SAME_RUN",
    "run_id": "m5-joint-synthetic", "execution_id": "exec-synthetic",
    "workflow_run_id": "workflow-synthetic",
    "worker_a_pid": 101, "worker_a_exit_code": -9,
    "worker_b_pid": 202, "b_worker_role": "worker-B",
    "native_retry_count": 1, "initial_epoch": 7, "new_epoch": 8,
    "a_cube_id": "native-sandbox", "b_cube_id": "native-sandbox",
    "guest_original_bytes_preserved": True, "old_epoch_rejected": True,
    "wrong_scope_rejected": True, "destroy_ack": "RELEASED",
}


def wait_status(client, jid):
    for _ in range(120):
        response = client.get(f"/api/verification/executions/{jid}",
                              headers={"X-Inspector-Scenario-Token": TOKEN})
        if response.json().get("status") not in ("QUEUED", "RUNNING"):
            return response
        time.sleep(.02)
    raise AssertionError("Synthetic execution not terminated")


class TrustedInspectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.calls = []

    def app(self, execute=None):
        if execute is None:
            execute = lambda: dict(PROOF)
        runner = TrustedScenarioRunner(
            token=TOKEN, evidence_dir=self.path, execute=execute,
        )
        return TestClient(create_app(trusted_runner=runner))

    def test_default_disabled_cannot_start_privileged_script(self):
        c = TestClient(create_app())
        self.assertEqual(c.post(
            "/api/verification/scenarios/worker-takeover/runs",
            headers={"X-Inspector-Scenario-Token": TOKEN}).status_code, 503)
        self.assertEqual(
            c.get("/api/verification/scenarios").json()["scenarios"][2]["availability"],
            "READ_ONLY_NOT_EXECUTABLE")

    def test_missing_or_wrong_token_is_rejected_without_execution(self):
        c = self.app(execute=lambda: self.calls.append("called"))
        endpoint = "/api/verification/scenarios/worker-takeover/runs"
        self.assertEqual(c.post(endpoint).status_code, 403)
        self.assertEqual(c.post(endpoint,headers={
            "X-Inspector-Scenario-Token": "bad"}).status_code, 403)
        # HTTP does not accept non-ASCII header bytes; verify fail-closed
        # handling at the authority boundary directly.
        self.assertFalse(TrustedScenarioRunner(
            token=TOKEN, evidence_dir=self.path).authorized("非ASCII"))
        self.assertEqual(c.post(endpoint,headers={
            "X-Inspector-Scenario-Token": TOKEN, "Origin": "https://attacker.example"
        }).status_code, 403)
        self.assertEqual(c.post("/api/verification/scenarios/tool-receipt/runs",
                                headers={"X-Inspector-Scenario-Token": TOKEN}).status_code, 404)
        self.assertEqual(self.calls, [])

    def test_opt_in_does_not_change_default_read_only_catalogue(self):
        privileged = self.app()
        self.assertEqual(privileged.get("/api/verification/scenarios").json()
                         ["scenarios"][2]["availability"],
                         "EXECUTABLE_OPERATOR_AUTH")
        default = TestClient(create_app())
        self.assertEqual(default.get("/api/verification/scenarios").json()
                         ["scenarios"][2]["availability"],
                         "READ_ONLY_NOT_EXECUTABLE")

    def test_authenticated_job_persists_only_validated_safe_evidence(self):
        c = self.app()
        endpoint = "/api/verification/scenarios/worker-takeover/runs"
        res = c.post(endpoint, headers={"X-Inspector-Scenario-Token": TOKEN})
        self.assertEqual(res.status_code, 202, res.text)
        jid = res.json()["execution_id"]
        self.assertNotIn(TOKEN, res.text)
        self.assertEqual(c.get(
            f"/api/verification/executions/{jid}").status_code, 403)
        done = wait_status(c, jid)
        self.assertEqual(done.status_code, 200)
        self.assertEqual(done.json()["status"], "PASSED")
        self.assertTrue(done.json()["verified"])
        self.assertEqual(done.json()["evidence"]["workflow_run_id"], "workflow-synthetic")
        self.assertNotIn('"guest_original":', done.text)
        self.assertNotIn(TOKEN, done.text)
        self.assertEqual(len(list(self.path.glob("*.json"))), 1)
        # Restarted server must read immutable persisted evidence rather than
        # advertise fabricated current-process state.
        c2 = self.app()
        self.assertEqual(wait_status(c2, jid).json()["status"], "PASSED")

    def test_untrustworthy_external_output_never_yields_pass(self):
        proof = dict(PROOF, worker_a_exit_code=0)
        c = self.app(execute=lambda: proof)
        r = c.post("/api/verification/scenarios/worker-takeover/runs",
                   headers={"X-Inspector-Scenario-Token": TOKEN})
        data = wait_status(c, r.json()["execution_id"]).json()
        self.assertEqual(data["status"], "BLOCKED_UNKNOWN")
        self.assertFalse(data["verified"])
        self.assertNotIn("traceback", str(data))
        self.assertEqual(c.post("/api/verification/scenarios/worker-takeover/runs",
                                headers={"X-Inspector-Scenario-Token": TOKEN}).status_code,409)

    def test_only_one_privileged_execution_can_run_at_once(self):
        from threading import Event
        begun, release = Event(), Event()
        def slow():
            begun.set()
            release.wait(4)
            return dict(PROOF)
        c = self.app(execute=slow)
        url = "/api/verification/scenarios/worker-takeover/runs"
        headers = {"X-Inspector-Scenario-Token": TOKEN}
        try:
            first = c.post(url, headers=headers)
            self.assertEqual(first.status_code, 202)
            self.assertTrue(begun.wait(2))
            self.assertEqual(c.post(url, headers=headers).status_code, 409)
        finally:
            release.set()
            if 'first' in locals() and first.status_code == 202:
                wait_status(c, first.json()["execution_id"])


if __name__ == "__main__":
    unittest.main()
