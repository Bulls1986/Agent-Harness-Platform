"""G3 deterministic SDK wire-contract test; NOT a real LiteLLM/model pass.

Exercises real pinned OpenAIChatClient / create_harness_agent / streaming,
a separate Uvicorn platform worker, PostgreSQL typed facts + SSE, then
a fresh Uvicorn process restoring the same persisted Run.
Only the OpenAI-compatible upstream endpoint is replaced by a loopback stub.
No real-provider credentials or network model calls are used.
"""
from __future__ import annotations

import json
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import uuid4

from task_ledger import TaskLedger
from verify_live_model_protocol import events_from_sse, exchange
from verify_selfhost_protocol import launch, stop

MODEL = "g3-wire-contract-stub"


class WireStub(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        # Never log prompts or Authorization headers.
        self.server.observed.append({
            "path": self.path,
            "stream": payload.get("stream"),
            "store": payload.get("store"),
            "model": payload.get("model"),
            "tools": payload.get("tools"),
            "nonce_present": self.server.nonce in json.dumps(payload),
        })
        if self.path != "/v1/responses":
            self.send_error(404)
            return
        if self.server.fail_next:
            # Provider error text may contain secrets; never forward it to SSE.
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": {"message": "fake-provider-secret-canary",
                                                   "type": "invalid_request_error"}}).encode())
            return
        nonce = self.server.nonce
        # Three distinct real HTTP SSE chunks; not a mocked MAF/adapter iterator.
        parts = [nonce[:5], nonce[5:11], nonce[11:]]
        response = {
            "id": "resp_wire_stub", "object": "response", "created_at": 1,
            "status": "completed", "model": MODEL, "output": [],
            "parallel_tool_calls": False, "tool_choice": "auto",
            "tools": [], "store": False,
            "usage": {"input_tokens": 2, "output_tokens": 3, "total_tokens": 5},
        }
        item = {
            "id": "msg_wire_stub", "type": "message", "status": "in_progress",
            "role": "assistant", "content": [],
        }
        events = []
        def add(kind, **fields):
            events.append({"type": kind, "sequence_number": len(events) + 1, **fields})

        add("response.created", response={**response, "status": "in_progress"})
        add("response.output_item.added", output_index=0, item=item)
        add("response.content_part.added", item_id=item["id"], output_index=0,
            content_index=0, part={"type": "output_text", "text": "", "annotations": []})
        for delta in parts:
            add("response.output_text.delta", item_id=item["id"],
                output_index=0, content_index=0, delta=delta)
        content = {"type": "output_text", "text": nonce, "annotations": []}
        add("response.output_text.done", item_id=item["id"],
            output_index=0, content_index=0, text=nonce)
        add("response.content_part.done", item_id=item["id"],
            output_index=0, content_index=0, part=content)
        finished = {**item, "status": "completed", "content": [content]}
        add("response.output_item.done", output_index=0, item=finished)
        add("response.completed", response={**response, "output": [finished]})

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            for event in events:
                body = "event: " + event["type"] + "\n"
                body += "data: " + json.dumps(event, separators=(",", ":")) + "\n\n"
                self.wfile.write(body.encode())
                self.wfile.flush()
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass


def main():
    dsn = os.getenv("POC_POSTGRES_DSN")
    if not dsn:
        raise SystemExit("Dedicated test-only PostgreSQL DSN required")
    TaskLedger(dsn).initialize()
    nonce = "G3STUB" + uuid4().hex[:15].upper()
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), WireStub)
    upstream.observed = []
    upstream.nonce = nonce
    upstream.fail_next = False
    thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    thread.start()

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    worker = None
    try:
        os.environ["POC_LITELLM_API_KEY"] = "wire-stub-dummy-never-real"
        os.environ["POC_LITELLM_MODEL"] = MODEL
        os.environ["POC_LITELLM_BASE_URL"] = f"http://127.0.0.1:{upstream.server_port}/v1"
        worker = launch(port)
        status, raw, _ = exchange(base + "/v1/live/responses",
                                  body={"input": "Echo " + nonce, "stream": True})
        stream = events_from_sse(raw)
        assert status == 200
        assert len(upstream.observed) == 1
        wire = upstream.observed[0]
        safe_wire = {key: (len(value or []) if key == "tools" else value)
                     for key, value in wire.items()}
        assert wire["path"] == "/v1/responses" and wire["stream"] is True \
            and wire["store"] is False and wire["model"] == MODEL \
            and wire["nonce_present"] is True and not wire["tools"], \
            f"MAF/OpenAI safe wire contract mismatch: {safe_wire}"
        assert stream and stream[0]["type"] == "run.started"
        assert [e["seq"] for e in stream] == list(range(1, len(stream) + 1))
        deltas = [e for e in stream if e["type"] == "response.output_text.delta"]
        assert len(deltas) == 3, "MAF SDK lost a real HTTP SSE fragment"
        assert "".join(e["data"]["delta"] for e in deltas) == nonce
        assert stream[-1]["type"] == "run.terminal"
        assert stream[-1]["data"]["state"] == "COMPLETED"
        run_id = stream[0]["run_id"]

        # Exercise the actual MAF/OpenAI SDK error route through the same
        # platform Run/Typed Event/SSE, with no secret error echo or retry.
        upstream.fail_next = True
        failed_status, failed_raw, _ = exchange(
            base + "/v1/live/responses",
            body={"input": "error-path stub probe", "stream": True},
        )
        failed = events_from_sse(failed_raw)
        assert failed_status == 200
        assert len(failed) == 2
        assert failed[0]["type"] == "run.started"
        assert failed[-1]["type"] == "run.terminal"
        assert failed[-1]["data"]["state"] == "FAILED"
        assert failed[-1]["data"]["failure_type"] == "MODEL_STREAM_INTERRUPTED"
        assert "fake-provider-secret-canary" not in failed_raw
        failed_run_id = failed[0]["run_id"]
        assert len(upstream.observed) == 2  # no provider retry on this failure

        stop(worker)
        worker = None
        # Second platform worker must restore purely from PostgreSQL, without
        # any provider credential/configuration or original worker memory.
        for name in ("POC_LITELLM_API_KEY", "POC_LITELLM_MODEL", "POC_LITELLM_BASE_URL"):
            os.environ.pop(name, None)
        worker = launch(port)
        _, raw_snapshot, _ = exchange(base + "/v1/responses/" + run_id)
        snapshot = json.loads(raw_snapshot)
        _, raw_replay, _ = exchange(base + "/v1/runs/" + run_id + "/events",
                                    headers={"Last-Event-ID": f"{run_id}:1"})
        replay = events_from_sse(raw_replay)
        assert snapshot["status"] == "completed"
        assert snapshot["output"][0]["content"][0]["text"] == nonce
        assert snapshot["harness"]["event_cursor"] == len(stream)
        assert replay == stream[1:]

        _, failed_snapshot_raw, _ = exchange(base + "/v1/responses/" + failed_run_id)
        failed_snapshot = json.loads(failed_snapshot_raw)
        _, failed_replay_raw, _ = exchange(
            base + "/v1/runs/" + failed_run_id + "/events",
            headers={"Last-Event-ID": f"{failed_run_id}:1"},
        )
        assert failed_snapshot["status"] == "failed"
        assert failed_snapshot["error"]["code"] == "MODEL_STREAM_INTERRUPTED"
        assert failed_snapshot["output"] == []
        assert events_from_sse(failed_replay_raw) == failed[1:]
        print(json.dumps({
            "outcome": "PASS_REAL_SDK_WITH_SIMULATED_UPSTREAM",
            "actual_maf_sdk": True, "actual_litellm": False,
            "simulated_upstream": True, "actual_pg": True,
            "real_http_worker_restarted": True,
            "delta_count": len(deltas), "persisted_event_count": len(stream),
            "platform_snapshot_matches_replay": True,
            "sdk_http_failure_terminal_verified": True,
            "provider_error_redacted": True,
        }, sort_keys=True))
    finally:
        stop(worker)
        upstream.shutdown()
        upstream.server_close()
        thread.join(timeout=3)
        for name in ("POC_LITELLM_API_KEY", "POC_LITELLM_MODEL", "POC_LITELLM_BASE_URL"):
            os.environ.pop(name, None)


if __name__ == "__main__":
    main()
