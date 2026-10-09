"""Optional REAL OpenCode-in-E2B smoke; never runs a model.

Requires: pip install e2b; E2B_API_KEY; OPENCODE_TEST_ALLOW_REMOTE=1.
For Cube use E2B_API_URL and CUBE_OPENCODE_TEMPLATE_ID; compatibility unproven.
"""
import argparse
import base64
import json
import os
import secrets
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--provider", choices=("e2b", "cube"), default="e2b")
    args = p.parse_args()
    template = ("opencode" if args.provider == "e2b"
                else os.environ.get("CUBE_OPENCODE_TEMPLATE_ID"))
    if args.provider == "cube":
        ready = bool(os.environ.get("E2B_API_URL") and template)
        reason = "Cube E2B-compatible URL or custom OpenCode template missing"
    else:
        ready = bool(os.environ.get("E2B_API_KEY") and
                     os.environ.get("OPENCODE_TEST_ALLOW_REMOTE") == "1")
        reason = "E2B_API_KEY or explicit remote-cost opt-in missing"
    if not ready:
        print(json.dumps({"outcome": "SKIP", "provider": args.provider,
                          "reason": reason}))
        return 2

    try:
        from e2b import Sandbox
    except ImportError:
        print(json.dumps({"outcome": "SKIP", "reason": "pip install e2b"}))
        return 2

    password = secrets.token_urlsafe(36)
    sandbox = None
    try:
        sandbox = Sandbox.create(template, envs={"OPENCODE_SERVER_PASSWORD": password},
                                 timeout=180)
        sandbox.commands.run("opencode serve --hostname 0.0.0.0 --port 4096",
                             background=True)
        host = sandbox.get_host(4096)
        base = "https://" + host
        basic = base64.b64encode(("opencode:" + password).encode()).decode()
        headers = {"Authorization": "Basic " + basic,
                   "Content-Type": "application/json"}

        def call(path, data=None):
            payload = json.dumps(data).encode() if data is not None else None
            req = Request(base + path, data=payload, headers=headers,
                          method="POST" if data is not None else "GET")
            with urlopen(req, timeout=8) as response:
                return json.load(response)

        deadline = time.monotonic() + 90
        while True:
            try:
                call("/global/health")
                break
            except (URLError, TimeoutError, HTTPError):
                if time.monotonic() > deadline:
                    raise TimeoutError("OpenCode HTTP health deadline")
                time.sleep(1)

        sessions = [call("/session", {"title": f"sandbox-smoke-{i}"})
                    for i in range(2)]
        assert len({x["id"] for x in sessions}) == 2
        listed = {x["id"] for x in call("/session")}
        assert {x["id"] for x in sessions} <= listed
        print(json.dumps({"outcome": "PASS", "provider": args.provider,
                          "sandbox_count": 1, "logical_sessions": 2,
                          "model_calls": 0, "tool_isolation": "NOT_TESTED"}))
        return 0
    finally:
        if sandbox is not None:
            sandbox.kill()


if __name__ == "__main__":
    raise SystemExit(main())