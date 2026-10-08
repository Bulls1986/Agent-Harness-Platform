"""G3 real self-hosted MAF/LiteLLM -> durable typed event -> SSE/restart gate.

Run from repository root with POC_POSTGRES_DSN set to a disposable database:
    python poc/maf/verify_live_model_protocol.py --model MODEL --base-url URL

Provide the LiteLLM API key as the first line of a trusted stdin pipe.
Never place credentials in argv, repo files, reports or stdout. This probe
prints only aggregate booleans/counters, never raw model output or secrets.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import urllib.request
from uuid import uuid4

from verify_selfhost_protocol import launch, stop


def exchange(url: str, *, body: dict | None = None,
             headers: dict | None = None) -> tuple[int, str, dict]:
    raw = None if body is None else json.dumps(body).encode("utf-8")
    request_headers = {"Content-Type": "application/json"} if raw is not None else {}
    request_headers.update(headers or {})
    req = urllib.request.Request(url, data=raw, headers=request_headers,
                                 method="POST" if raw is not None else "GET")
    with urllib.request.urlopen(req, timeout=150) as result:
        return result.status, result.read().decode("utf-8"), dict(result.headers)


def events_from_sse(stream: str) -> list[dict]:
    events = []
    for block in stream.split("\n\n"):
        data = next((line[6:] for line in block.splitlines() if line.startswith("data: ")), None)
        if data:
            events.append(json.loads(data))
    return events


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()
    key = sys.stdin.readline().strip()
    if not key or not os.getenv("POC_POSTGRES_DSN"):
        print(json.dumps({"outcome": "SETUP_GAP", "reason": "stdin key and PG DSN required"}))
        return 2

    # The key is injected into a short-lived, loopback-only Uvicorn subprocess.
    os.environ["POC_LITELLM_API_KEY"] = key
    os.environ["POC_LITELLM_MODEL"] = args.model
    os.environ["POC_LITELLM_BASE_URL"] = args.base_url
    sys.path.insert(0, os.path.join(os.getcwd(), "poc", "maf"))
    from task_ledger import TaskLedger
    TaskLedger(os.environ["POC_POSTGRES_DSN"]).initialize()
    nonce = "G3-" + uuid4().hex[:12].upper()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    server = None
    try:
        server = launch(port)
        status, raw, _ = exchange(base + "/v1/live/responses", body={
            "input": "Reply with this reference code only: " + nonce, "stream": True,
        })
        stream = events_from_sse(raw)
        if not stream:
            raise AssertionError("No platform SSE events received")
        run_id = stream[0]["run_id"]
        deltas = [e for e in stream if e["type"] == "response.output_text.delta"]
        if not deltas or not any(e["type"] == "run.terminal" and
                                 e["data"]["state"] == "COMPLETED" for e in stream):
            raise AssertionError("Actual provider stream did not finish successfully")
        if [event["seq"] for event in stream] != list(range(1, len(stream) + 1)):
            raise AssertionError("Live SSE sequence is not contiguous")
        if nonce not in "".join(e["data"]["delta"] for e in deltas):
            raise AssertionError("Provider did not echo the requested randomized marker")

        # A genuinely different HTTP process now reconstructs output from PG.
        stop(server)
        server = None
        os.environ.pop("POC_LITELLM_API_KEY", None)
        server = launch(port)
        _, snapshot_raw, _ = exchange(base + "/v1/responses/" + run_id)
        snapshot = json.loads(snapshot_raw)
        _, replay_raw, _ = exchange(base + "/v1/runs/" + run_id + "/events",
                                     headers={"Last-Event-ID": f"{run_id}:1"})
        replay = events_from_sse(replay_raw)
        assert status == 200
        assert snapshot["status"] == "completed"
        assert snapshot["harness"]["real_model_invoked"]
        assert snapshot["harness"]["event_cursor"] == len(stream)
        assert len(replay) == len(stream) - 1
        assert [e["seq"] for e in replay] == list(range(2, len(stream) + 1))
        assert snapshot["output"][0]["content"][0]["text"] == "".join(
            e["data"]["delta"] for e in deltas
        )
        print(json.dumps({
            "outcome": "PASS", "real_model_invoked": True,
            "live_delta_count": len(deltas), "persisted_event_count": len(stream),
            "nonce_echo_verified": True, "sse_cursor_replay_verified": True,
            "http_process_restarted": True, "raw_model_output_logged": False
        }, sort_keys=True))
        return 0
    except Exception as exc:
        # Do not leak provider exception text; it may include the secret.
        print(json.dumps({"outcome": "GAP", "exception_type": type(exc).__name__}))
        return 1
    finally:
        stop(server)
        os.environ.pop("POC_LITELLM_API_KEY", None)


if __name__ == "__main__":
    raise SystemExit(main())
