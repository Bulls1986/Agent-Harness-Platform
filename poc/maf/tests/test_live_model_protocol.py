"""G3: live token translation must preserve actual provider chunks and durable order."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from live_model_protocol import persisted_model_events
from protocol_service import _event, _response, _sse, app
from fastapi.testclient import TestClient


class RecordingLedger:
    def __init__(self):
        self.rows = []
        self.end = None

    def append_delta(self, run_id, step_id, attempt_id, delta):
        row = {"seq": len(self.rows) + 2,
               "event_type": "response.output_text.delta",
               "payload": {"step_id": step_id, "attempt_id": attempt_id, "delta": delta}}
        self.rows.append(row)
        return row

    def terminate(self, run_id, attempt_id, execution_id, *, completed, failure_type=None):
        self.end = (completed, failure_type)
        return {"seq": len(self.rows) + 2, "event_type": "run.terminal",
                "payload": {"state": "COMPLETED" if completed else "FAILED",
                            "failure_type": failure_type, "attempt_id": attempt_id}}


async def chunks(*parts):
    for part in parts:
        yield part


async def exploding_chunks():
    yield "genuine"
    raise RuntimeError("never expose sk-SENSITIVE-SECRET provider exception")


class LiveProtocolUnitTests(unittest.TestCase):
    def _consume(self, fake):
        ledger = RecordingLedger()
        with patch("live_model_protocol.provider_deltas", fake):
            rows = asyncio.run(collect(ledger))
        return ledger, rows

    def test_mocked_provider_chunks_are_persisted_before_they_are_published(self):
        ledger = RecordingLedger()

        async def observe():
            seen = []
            async for row in persisted_model_events(
                ledger, run_id="r", step_id="s", attempt_id="a",
                execution_id="e", prompt="hello", model="m",
                base_url="unused", api_key="never-print"
            ):
                if row["event_type"] == "response.output_text.delta":
                    self.assertIn(row, ledger.rows)  # commit before SSE
                seen.append(row)
            return seen

        with patch("live_model_protocol.provider_deltas", lambda **kw: chunks("hi", " ", "there")):
            rows = asyncio.run(observe())
        self.assertEqual("".join(r["payload"]["delta"] for r in ledger.rows), "hi there")
        self.assertEqual([r["seq"] for r in rows], [2, 3, 4, 5])
        self.assertEqual(ledger.end, (True, None))
        self.assertEqual(rows[-1]["payload"]["state"], "COMPLETED")

    def test_provider_failure_preserves_partial_tokens_and_no_leaked_error(self):
        ledger = RecordingLedger()
        with patch("live_model_protocol.provider_deltas", lambda **kw: exploding_chunks()):
            rows = asyncio.run(collect(ledger))
        self.assertEqual(ledger.end, (False, "MODEL_STREAM_INTERRUPTED"))
        self.assertEqual(len(ledger.rows), 1)
        self.assertNotIn("SENSITIVE-SECRET", json.dumps(rows))

    def test_empty_stream_is_not_a_success(self):
        ledger = RecordingLedger()
        with patch("live_model_protocol.provider_deltas", lambda **kw: chunks()):
            rows = asyncio.run(collect(ledger))
        self.assertEqual(ledger.end, (False, "EMPTY_MODEL_STREAM"))
        self.assertEqual([r["event_type"] for r in rows], ["run.terminal"])

    def test_responses_snapshot_derived_only_from_persisted_deltas(self):
        record = {"run": {"run_id": "r", "state": "COMPLETED",
                          "recipe_version": "poc-live-model-v1"},
                  "events": [
                      {"seq": 1, "event_type": "run.started", "payload": {"model": "real"}},
                      {"seq": 2, "event_type": "response.output_text.delta", "payload": {"delta": "ab"}},
                      {"seq": 3, "event_type": "response.output_text.delta", "payload": {"delta": "cd"}},
                      {"seq": 4, "event_type": "run.terminal", "payload": {"state": "COMPLETED"}},
                  ]}
        snapshot = _response(record)
        self.assertEqual(snapshot["output"][0]["content"][0]["text"], "abcd")
        self.assertEqual(snapshot["model"], "real")
        self.assertTrue(snapshot["harness"]["real_model_invoked"])
        self.assertFalse(snapshot["harness"]["fixture_only"])
        event = _event(record["events"][1], "r")
        self.assertEqual(event["id"], "r:2")
        self.assertIn("event: response.output_text.delta\n", _sse(event))


    def test_disconnected_model_stream_never_reports_success(self):
        async def interrupted():
            yield "partial"
            raise asyncio.CancelledError()

        ledger = RecordingLedger()
        with patch("live_model_protocol.provider_deltas", lambda **kw: interrupted()):
            with self.assertRaises(asyncio.CancelledError):
                asyncio.run(collect(ledger))
        self.assertEqual(ledger.end, (False, "STREAM_DISCONNECTED"))
        self.assertEqual(len(ledger.rows), 1)

    def test_consumer_closes_stream_midflight_leaves_no_running_run(self):
        ledger = RecordingLedger()

        async def close_early():
            stream = persisted_model_events(
                ledger, run_id="r", step_id="s", attempt_id="a",
                execution_id="e", prompt="hello", model="m",
                base_url="unused", api_key="not-a-real-key"
            )
            first = await anext(stream)
            self.assertEqual(first["event_type"], "response.output_text.delta")
            await stream.aclose()

        with patch("live_model_protocol.provider_deltas", lambda **kw: chunks("first", "second")):
            asyncio.run(close_early())
        self.assertEqual(ledger.end, (False, "STREAM_DISCONNECTED"))
        self.assertEqual(len(ledger.rows), 1)

    def test_live_model_admission_and_loopback_restrictions(self):
        local = TestClient(app)
        with patch.dict(os.environ, {"POC_LITELLM_API_KEY": "",
                                     "POC_LITELLM_BASE_URL": "",
                                     "POC_LITELLM_MODEL": ""}):
            self.assertEqual(local.post("/v1/live/responses",
                             json={"input": "hello", "stream": True}).status_code, 503)
        with patch.dict(os.environ, {"POC_LITELLM_API_KEY": "test-only",
                                     "POC_LITELLM_BASE_URL": "http://unused.invalid/v1",
                                     "POC_LITELLM_MODEL": "admitted"}):
            self.assertEqual(local.post("/v1/live/responses",
                             json={"input": "hello", "model": "unapproved", "stream": True}).status_code, 422)
            self.assertEqual(local.post("/v1/live/responses",
                             json={"input": "hello", "stream": False}).status_code, 422)
            self.assertEqual(local.post("/v1/live/responses",
                             json={"input": "hello", "stream": True, "tools": []}).status_code, 422)
            remote = TestClient(app, client=("192.0.2.10", 40000))
            self.assertEqual(remote.post("/v1/live/responses",
                             json={"input": "hello", "stream": True}).status_code, 403)
        self.assertTrue(local.get("/health").json()["fixture_only"])

    def test_sse_last_event_id_is_run_scoped_and_replays_durably(self):
        records = {"run": {"run_id": "r", "state": "COMPLETED",
                           "recipe_version": "poc-live-model-v1"},
                   "events": [
                       {"seq": 1, "event_type": "run.started", "payload": {"model": "m"}},
                       {"seq": 2, "event_type": "response.output_text.delta", "payload": {"delta": "a"}},
                       {"seq": 3, "event_type": "run.terminal", "payload": {"state": "COMPLETED"}},
                   ]}
        class FakeLedger:
            def read(self, run_id):
                if run_id != "r":
                    raise KeyError(run_id)
                return records

        with patch("protocol_service._ledger", return_value=FakeLedger()):
            client = TestClient(app)
            replay = client.get("/v1/runs/r/events", headers={"Last-Event-ID": "r:1"})
            self.assertEqual(replay.status_code, 200)
            self.assertNotIn("event: run.started", replay.text)
            self.assertIn("id: r:2", replay.text)
            self.assertIn("id: r:3", replay.text)
            self.assertEqual(client.get("/v1/runs/r/events",
                            headers={"Last-Event-ID": "other:1"}).status_code, 422)
            self.assertEqual(client.get("/v1/runs/r/events?after=2",
                            headers={"Last-Event-ID": "r:1"}).status_code, 422)
            self.assertEqual(client.get("/v1/runs/r/events",
                            headers={"Last-Event-ID": "r:" + "9" * 5000}).status_code, 422)
            self.assertEqual(client.get("/v1/runs/r/events",
                            headers={"Last-Event-ID": "r:2147483648"}).status_code, 422)
            self.assertEqual(client.get("/v1/runs/r/events?after=3").text, "")


async def collect(ledger):
    rows = []
    async for row in persisted_model_events(
        ledger, run_id="r", step_id="s", attempt_id="a",
        execution_id="e", prompt="hello", model="m",
        base_url="unused", api_key="do-not-output"
    ):
        rows.append(row)
    return rows


@unittest.skipUnless(os.environ.get("POC_POSTGRES_DSN"), "needs local PostgreSQL")
class LiveProtocolPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from live_model_protocol import LiveModelLedger
        cls.ledger = LiveModelLedger(os.environ["POC_POSTGRES_DSN"])
        cls.ledger.initialize()

    def test_http_sse_to_durable_snapshot_and_reconnect(self):
        async def real_chunks_fixture(**kw):
            # Explicit test double, never claimed as a real provider.
            for part in ("observed", " ", "chunks"):
                yield part

        with patch.dict(os.environ, {"POC_LITELLM_MODEL": "fixture",
                                     "POC_LITELLM_BASE_URL": "http://not-contacted.invalid/v1",
                                     "POC_LITELLM_API_KEY": "test-only"}), \
             patch("live_model_protocol.provider_deltas", real_chunks_fixture):
            client = TestClient(app)
            streamed = client.post("/v1/live/responses",
                                   json={"input": "controlled mock request", "stream": True})
            self.assertEqual(streamed.status_code, 200, streamed.text)
            run_id = streamed.headers["X-Harness-Run-Id"]
            self.assertEqual(streamed.text.count("event: response.output_text.delta"), 3)
            snapshot = client.get("/v1/responses/" + run_id).json()
            self.assertEqual(snapshot["status"], "completed")
            self.assertEqual(snapshot["output"][0]["content"][0]["text"], "observed chunks")
            self.assertEqual(snapshot["harness"]["event_cursor"], 5)
            replay = client.get("/v1/runs/" + run_id + "/events",
                                headers={"Last-Event-ID": run_id + ":3"})
            self.assertIn("id: " + run_id + ":4", replay.text)
            self.assertIn("id: " + run_id + ":5", replay.text)
            self.assertNotIn("id: " + run_id + ":3\n", replay.text)
