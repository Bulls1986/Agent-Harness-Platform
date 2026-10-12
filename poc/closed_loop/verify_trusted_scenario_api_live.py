"""DEV-M5 B.3 actual Inspector authorization -> native B03 -> durable evidence.

Run only on authorized Linux with real Cube + both PostgreSQL endpoints.
Synthetic test data only. This is NOT a fake success-path TestClient callback.
No credentials are persisted or printed.
"""
from __future__ import annotations

import json
import secrets
import tempfile
import time

from fastapi.testclient import TestClient

from poc.closed_loop.inspector import create_app
from poc.closed_loop.trusted_scenario_runner import TrustedScenarioRunner


def verify() -> dict:
    with tempfile.TemporaryDirectory(prefix="ahp-b3-native-") as root:
        token = secrets.token_urlsafe(48)
        app = create_app(trusted_runner=TrustedScenarioRunner(
            token=token, evidence_dir=root))
        client = TestClient(app)
        route = "/api/verification/scenarios/worker-takeover/runs"
        if client.post(route).status_code != 403:
            raise AssertionError("Anonymous physical scenario was admitted")
        if client.post(route, headers={
                "X-Inspector-Scenario-Token": "invalid"}).status_code != 403:
            raise AssertionError("Incorrect operator authorization was admitted")
        if (client.get("/api/verification/scenarios").json()
                ["scenarios"][2]["availability"] != "EXECUTABLE_OPERATOR_AUTH"):
            raise AssertionError("Inspector did not expose authorized capability")

        headers = {"X-Inspector-Scenario-Token": token}
        response = client.post(route, headers=headers)
        if response.status_code != 202:
            raise AssertionError("Native physical scenario not admitted")
        execution_id = response.json()["execution_id"]
        deadline = time.monotonic() + 250
        while time.monotonic() < deadline:
            result = client.get(
                "/api/verification/executions/" + execution_id,
                headers=headers)
            if result.status_code != 200:
                raise AssertionError("Operator cannot query durable evidence")
            record = result.json()
            if record["status"] != "RUNNING":
                break
            time.sleep(2)
        else:
            raise TimeoutError("Real Inspector B03 did not reach terminal")
        if record["status"] != "PASSED" or record["verified"] is not True:
            raise AssertionError("Live privileged B03 failed; inspect server-side evidence")
        proof = record["evidence"]
        if (proof["a_cube_id"] != proof["b_cube_id"]
                or proof["worker_a_exit_code"] != -9
                or proof["native_retry_count"] < 1
                or proof["destroy_ack"] != "RELEASED"):
            raise AssertionError("Actual provider evidence not correlated")
        restarted = TestClient(create_app(
            trusted_runner=TrustedScenarioRunner(token=token, evidence_dir=root)))
        reread = restarted.get(
            "/api/verification/executions/" + execution_id, headers=headers)
        if reread.json().get("status") != "PASSED":
            raise AssertionError("Immutable completed proof did not survive restart")
        return {
            "outcome": "PASS_REAL_INSPECTOR_TRUSTED_B03_API",
            "evidence_id": execution_id,
            "run_id": proof["run_id"],
            "workflow_run_id": proof["workflow_run_id"],
            "sandbox_id": proof["a_cube_id"],
            "worker_a_pid": proof["worker_a_pid"],
            "worker_a_exit_code": proof["worker_a_exit_code"],
            "worker_b_pid": proof["worker_b_pid"],
            "native_retry_count": proof["native_retry_count"],
            "durable_evidence_after_restart": True,
            "anonymous_and_bad_token_denied": True,
        }


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True), flush=True)
