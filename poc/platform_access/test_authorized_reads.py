"""DEV-M7: trusted gateway identity + per-Run policy contract (unit slice)."""
import unittest

from fastapi.testclient import TestClient

from poc.platform_access.authorized_reads import (
    RunBinding,
    SecurityContext,
    create_read_app,
)


class MemoryRunReader:
    def __init__(self):
        self.calls = []
        self.bindings = {
            "run-1": RunBinding("run-1", "project-A", "user-A"),
            "run-2": RunBinding("run-2", "project-B", "user-B"),
        }

    def binding(self, run_id):
        self.calls.append(("binding", run_id))
        return self.bindings[run_id]

    def snapshot(self, run_id):
        self.calls.append(("snapshot", run_id))
        return {"run_id": run_id, "input_prompt": "sensitive input", "result": {"text": "secret"}}

    def events_since(self, run_id, after, limit):
        self.calls.append(("events", run_id, after, limit))
        return [{"seq": after + 1, "type": "response.output_text.delta",
                 "data": {"delta": "secret"}}]


class AuthorizedReadContractTests(unittest.TestCase):
    def setUp(self):
        self.reader = MemoryRunReader()
        self.current = SecurityContext("user-A", "USER", "project-A")
        self.allowed = True
        self.policy_calls = []

        def gateway_identity(_request):
            return self.current

        def policy(context, binding, action):
            self.policy_calls.append((context.principal_id, binding.run_id, action))
            return self.allowed

        self.client = TestClient(create_read_app(
            resolve_context=gateway_identity, reader=self.reader, authorize=policy
        ))

    def test_authorized_run_and_event_cursor(self):
        detail = self.client.get("/api/runs/run-1")
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertEqual(detail.json()["result"]["text"], "secret")
        event = self.client.get("/api/runs/run-1/events?after=3&limit=5")
        self.assertEqual(event.status_code, 200, event.text)
        self.assertEqual(event.json()["cursor"], 4)
        self.assertEqual(self.policy_calls, [
            ("user-A", "run-1", "run.read"),
            ("user-A", "run-1", "run.events.read"),
        ])

    def test_cross_project_and_revoked_access_deny_before_payload_read(self):
        for suffix in ("", "/events?after=0"):
            response = self.client.get("/api/runs/run-2" + suffix)
            self.assertEqual(response.status_code, 404)
            self.assertNotIn("secret", response.text)
        self.assertEqual(self.policy_calls, [])  # project boundary is hard guard
        self.assertFalse(any(c[0] in ("snapshot", "events") for c in self.reader.calls))

        self.reader.calls.clear()
        self.allowed = False  # authorization is reevaluated on every request
        response = self.client.get("/api/runs/run-1/events")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.policy_calls, [("user-A", "run-1", "run.events.read")])
        self.assertFalse(any(c[0] == "events" for c in self.reader.calls))

    def test_no_identity_or_spoofed_headers_fail_closed(self):
        self.current = None
        response = self.client.get("/api/runs/run-1", headers={
            "X-Principal-Id": "user-A", "X-Project-Scope": "project-A",
        })
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.reader.calls, [])

    def test_missing_run_indistinguishable_from_denied_run(self):
        missing = self.client.get("/api/runs/absent")
        denied = self.client.get("/api/runs/run-2")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json(), denied.json())

    def test_bad_cursor_does_not_read_events(self):
        for cursor in ("-1", "not-a-number"):
            response = self.client.get("/api/runs/run-1/events?after=" + cursor)
            self.assertEqual(response.status_code, 422)
        self.assertEqual(self.reader.calls, [])

    def test_missing_project_scope_denied_without_run_lookup(self):
        self.current = SecurityContext("user-A", "USER", None)
        response = self.client.get("/api/runs/run-1")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.reader.calls, [])

    def test_policy_requires_explicit_true_and_missing_adapter_is_invalid(self):
        app = create_read_app(resolve_context=lambda _: self.current,
                              reader=self.reader,
                              authorize=lambda *_: "ALLOW")
        response = TestClient(app).get("/api/runs/run-1")
        self.assertEqual(response.status_code, 404)
        self.assertFalse(any(c[0] == "snapshot" for c in self.reader.calls))
        with self.assertRaises(ValueError):
            create_read_app(resolve_context=None, reader=self.reader, authorize=None)

    def test_run_binding_must_match_the_requested_run(self):
        self.reader.bindings["run-1"] = RunBinding("run-2", "project-A", "user-A")
        response = self.client.get("/api/runs/run-1")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.policy_calls, [])


if __name__ == "__main__":
    unittest.main()
