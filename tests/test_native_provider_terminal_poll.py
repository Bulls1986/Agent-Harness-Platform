"""Hatchet workflow result and terminal status may become visible separately.

Never treat a task result, cancellation ACK, string status or transient RUNNING
as a trusted provider COMPLETED fact.
"""
from enum import Enum
import unittest

from poc.closed_loop.facts import UnsafeDispatch
from poc.closed_loop.native_completion_gate import await_native_completed


class State(Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class NativeTerminalPollTests(unittest.TestCase):
    def test_eventual_native_completed_is_observed(self):
        observed = []
        statuses = iter([State.RUNNING, State.RUNNING, State.COMPLETED])

        def probe(provider_id):
            observed.append(provider_id)
            return next(statuses)

        value = await_native_completed(probe, "old-provider",
                                       timeout_secs=2, poll_interval_secs=.001)
        self.assertEqual(value, State.COMPLETED)
        self.assertEqual(observed, ["old-provider"] * 3)

    def test_fake_string_completed_is_not_authoritative(self):
        with self.assertRaises(UnsafeDispatch):
            await_native_completed(lambda _: "COMPLETED", "provider",
                                   timeout_secs=.01)

    def test_failure_and_cancel_cannot_be_promoted(self):
        for state in (State.FAILED, State.CANCELLED):
            with self.subTest(state=state):
                with self.assertRaises(UnsafeDispatch):
                    await_native_completed(lambda _: state, "provider",
                                           timeout_secs=.01)

    def test_running_never_fakes_completed_at_deadline(self):
        with self.assertRaises(UnsafeDispatch):
            await_native_completed(lambda _: State.RUNNING, "provider",
                                   timeout_secs=.003, poll_interval_secs=.001)


if __name__ == "__main__":
    unittest.main()
