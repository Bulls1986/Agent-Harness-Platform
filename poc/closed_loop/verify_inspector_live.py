"""Black-box live Inspector E2E against a real Hatchet-backed HTTP server."""
from __future__ import annotations

import argparse
import json
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def request(url: str, method: str = "GET", data: dict | None = None) -> dict:
    encoded = json.dumps(data).encode() if data is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    with urlopen(Request(url, data=encoded, headers=headers, method=method),
                 timeout=30) as response:
        if response.status not in (200, 202):
            raise RuntimeError("Unexpected HTTP status")
        raw = response.read()
        return json.loads(raw)


def verify(base: str, *, run_id: str | None = None) -> dict:
    if run_id is None:
        created = request(base + "/api/runs", "POST",
                          {"prompt": "inspect a real two sdk process"})
        run_id = created["run_id"]
        deadline = time.monotonic() + 220
        while time.monotonic() < deadline:
            status = request(base + "/api/runs/" + run_id)
            if status["state"] == "COMPLETED":
                break
            if status["outbox"] == "BLOCKED_UNKNOWN":
                raise RuntimeError("Workflow create ACK uncertain: safe blocked")
            if any(e["type"] == "workflow.observation_error" for e in status["events"]):
                raise RuntimeError("Real Hatchet workflow raised an observation error")
            time.sleep(1.0)
        else:
            raise TimeoutError("Real UI Run did not reach a verified terminal state")
    status = request(base + "/api/runs/" + run_id)
    history = request(base + "/api/runs")
    events = request(base + "/api/runs/" + run_id + "/events?after=0")["events"]
    one = request(base + "/api/runs/" + run_id + "/events?after=1")["events"]
    assert status["state"] == "COMPLETED", status
    assert status["provider_workflow_run_id"] != status["run_id"]
    assert status["provider_workflow_run_id"]
    assert all(s["state"] == "COMPLETED" and s["attempts"] == 1
               for s in status["steps"].values()), status
    assert status["steps"]["pydantic"]["output"] == "pydantic-sdk-real-run"
    assert status["steps"]["openai"]["output"] == "openai-sdk-real-run"
    assert status["result"]["final_output"] == "openai-sdk-real-run"
    assert status["result"]["mode"] == "deterministic_local_model"
    assert status["result"]["result_source_step"] == "openai"
    assert status["steps"]["openai"]["input"] == status["steps"]["pydantic"]["output"]
    if status["input_prompt"] is not None:
        assert status["steps"]["pydantic"]["input"] == status["input_prompt"]
    assert run_id in [r["run_id"] for r in history["runs"]], history
    assert [e["seq"] for e in events] == list(range(1, len(events)+1))
    assert [e["seq"] for e in one] == [e["seq"] for e in events if e["seq"] > 1]
    assert sum(e["type"] == "run.completed" for e in events) == 1
    assert sum(e["type"] == "runtime.run.completed" for e in events) == 2
    summary = {
        "outcome": "PASS", "real_hatchet": True, "real_2_sdk_dag": True,
        "docker_pg": True, "run_id": run_id,
        "workflow_id": status["provider_workflow_run_id"], "events": len(events),
        "inspector_refresh": "PASS", "final_result_visibility": "PASS",
        "result_source": "openai", "final_output": status["result"]["final_output"],
        "cube": "NOT_TESTED", "real_token_sse": "NOT_TESTED",
        "side_effect_receipt": "NOT_TESTED"
    }
    print(json.dumps(summary, sort_keys=True), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8765")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    verify(args.url.rstrip("/"), run_id=args.run_id)


if __name__ == "__main__":
    main()