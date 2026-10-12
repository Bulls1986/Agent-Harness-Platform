"""A genuine Cube MicroVM create can take the full native SDK timeout.

The Hatchet task/CLI watchdog must not expire before the native create can
finish, plus leave space for Guest files and controlled OS fault injection.
"""
import unittest

from poc.sandbox.cube_binding import CUBE_NATIVE_CREATE_TIMEOUT_SECONDS
from poc.sandbox.verify_hatchet_cube_worker_takeover import (
    HATCHET_TASK_TIMEOUT_SECONDS,
)


class M5LiveWorkerTimeBudgetTests(unittest.TestCase):
    def test_native_create_cannot_outlast_hatchet_task(self):
        self.assertGreaterEqual(
            HATCHET_TASK_TIMEOUT_SECONDS,
            CUBE_NATIVE_CREATE_TIMEOUT_SECONDS + 120,
        )


if __name__ == "__main__":
    unittest.main()
