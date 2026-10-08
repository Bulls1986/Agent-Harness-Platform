"""Local G3 launcher: disposable database and zero provider secrets in argv."""
from __future__ import annotations

import io
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_live_g3_local as probe


class LocalG3LauncherTests(unittest.TestCase):
    def test_missing_key_never_starts_docker(self):
        with patch.dict(os.environ, {
            "POC_LITELLM_API_KEY": "",
            "POC_LITELLM_BASE_URL": "http://stub.invalid/v1",
            "POC_LITELLM_MODEL": "stub",
        }), patch.object(probe, "_docker", side_effect=AssertionError("docker must not start")):
            # Windows User env currently does not hold a G3 key.
            with patch.object(probe, "_prepare_config",
                              return_value=["POC_LITELLM_API_KEY"]):
                with patch("sys.stdout", new_callable=io.StringIO) as out:
                    self.assertEqual(probe.main(), 2)
                self.assertIn("POC_LITELLM_API_KEY", out.getvalue())

    def test_temporary_password_is_never_sent_in_docker_argv(self):
        calls = []
        key = "fake-provider-key-not-for-network"

        def docker(*args, env=None, timeout=30):
            calls.append((args, env))
            if args[0] == "port":
                return "127.0.0.1:55551"
            return "test-id"

        def run(argv, **kw):
            calls.append((argv, kw.get("env")))
            if argv[0] == "docker":
                return SimpleNamespace(returncode=0)
            self.assertIn("POC_POSTGRES_DSN", kw["env"])
            self.assertEqual(kw["env"]["POC_LITELLM_API_KEY"], key)
            self.assertNotIn(key, " ".join(argv))
            return SimpleNamespace(returncode=0)

        with patch.dict(os.environ, {
            "POC_LITELLM_API_KEY": key,
            "POC_LITELLM_BASE_URL": "http://stub.invalid/v1",
            "POC_LITELLM_MODEL": "stub",
        }), patch.object(probe, "_docker", side_effect=docker), \
             patch.object(probe.subprocess, "run", side_effect=run):
            self.assertEqual(probe.main(), 0)
        self.assertEqual([a[0][0] for a in calls if a[0][0] in ("run", "port", "rm")],
                         ["run", "port", "rm"])
        docker_run_args = next(x[0] for x in calls if x[0][0] == "run")
        self.assertIn("POSTGRES_PASSWORD", docker_run_args)
        self.assertNotIn(key, " ".join(docker_run_args))


if __name__ == "__main__":
    unittest.main()
