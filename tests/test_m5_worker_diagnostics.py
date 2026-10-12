"""The physical takeover gate must retain real native Worker stderr.

Otherwise a registration failure looks like a hung Sandbox allocator.
"""
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from poc.sandbox.verify_hatchet_cube_worker_takeover import launch_worker


class WorkerDiagnosticsTests(unittest.TestCase):
    def test_worker_logs_are_not_discarded_to_devnull(self):
        with tempfile.TemporaryDirectory() as logdir:
            with patch.dict(os.environ, {"HARNESS_M5_WORKER_LOG_DIR": logdir}):
                with patch("subprocess.Popen") as popen:
                    launch_worker("worker-A")
                    kwargs = popen.call_args.kwargs
                    self.assertNotEqual(kwargs["stdout"], subprocess.DEVNULL)
                    self.assertEqual(kwargs["stderr"], subprocess.STDOUT)
                    self.assertTrue(os.listdir(logdir))


if __name__ == "__main__":
    unittest.main()
