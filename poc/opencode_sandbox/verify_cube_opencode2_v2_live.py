"""Opt-in LIVE OpenCode 2 V2 Session/FS/Shell on a REAL Cube MicroVM.

Uses ONLY public Cube Native SDK. The supplied Guest template must be READY,
contain OpenCode 2 and envd, and expose port 4096; no E2B client or remote LLM.
The V2 HTTP checks run over Guest loopback, without wildcard DNS/TLS shortcuts.
"""
from __future__ import annotations
import argparse
import json
import os
import secrets
import shlex
import time

GUEST_CHECK = r"""
import base64
import json
import os
import time
from urllib.request import Request, urlopen

pwd = os.environ["AHPOC_PASSWORD"]
basic = base64.b64encode(("opencode:" + pwd).encode()).decode("ascii")
headers = {"Authorization": "Basic " + basic, "Content-Type": "application/json"}

def req(path, data=None):
    payload = None if data is None else json.dumps(data).encode("utf-8")
    request = Request("http://127.0.0.1:4096" + path, data=payload, headers=headers,
                      method="GET" if data is None else "POST")
    with urlopen(request, timeout=9) as resp:
        raw = resp.read().decode("utf-8")
        # V2 FS read may return plain text; session/shell APIs return JSON.
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw

deadline = time.monotonic() + 75
while True:
    try:
        req("/api/session")
        break
    except Exception:
        if time.monotonic() >= deadline:
            print(json.dumps({"outcome":"FAIL", "stage":"server_http_ready"}))
            raise SystemExit(3)
        time.sleep(1)
try:
    current_stage = "create_session_1"
    one = req("/api/session", {"location":{"directory":"/workspace"}})
    current_stage = "create_session_2"
    two = req("/api/session", {"location":{"directory":"/workspace"}})
    sid1, sid2 = one["data"]["id"], two["data"]["id"]
    assert sid1 != sid2
    current_stage = "v2_fs_read"
    read = req("/api/fs/read/from_provider.txt")
    assert "provider-before" in json.dumps(read), "FS mismatch"
    current_stage = "v2_shell"
    shell = req("/api/shell", {"command":"printf v2-shell-ok > /workspace/from_v2_shell.txt",
                              "cwd":"/workspace","timeout":15000,"metadata":{}})
    print(json.dumps({"outcome":"PASS", "v2_sessions":2, "distinct": True,
                      "v2_fs_read":"PASS", "v2_shell_request":"PASS",
                      "v2_shell_result_status":shell.get("data",{}).get("status","unknown")},
                     sort_keys=True))
except Exception as exc:
    print(json.dumps({"outcome":"FAIL","stage":current_stage,
                      "http_code":getattr(exc,"code",None),
                      "exception_type":type(exc).__name__},sort_keys=True))
    raise SystemExit(4)
"""


def emit(**kw):
    print(json.dumps(kw, sort_keys=True, ensure_ascii=False), flush=True)


def main():
    arg = argparse.ArgumentParser()
    arg.add_argument("--live", action="store_true")
    arg.add_argument("--require-git", action="store_true")
    arg.add_argument("--template", default=os.getenv("CUBE_TEMPLATE_ID", ""))
    args = arg.parse_args()
    if not args.live:
        emit(outcome="PASS", scope="offline_config_only",
             real_cube="NOT_RUN", template_provided=bool(args.template))
        return 0
    if os.getenv("CUBE_NATIVE_LIVE_CONFIRM") != "1" or not args.template:
        emit(outcome="BLOCKED", reason="template and live confirmation required")
        return 2
    url = os.getenv("CUBE_API_URL", "")
    if not (url.startswith("http://127.0.0.1:") or
            url.startswith("http://localhost:") or url.startswith("https://")):
        emit(outcome="BLOCKED", reason="trusted Cube API endpoint required")
        return 2
    from cubesandbox import Sandbox
    sb = None
    try:
        sb = Sandbox.create(template=args.template, timeout=180)
        emit(stage="cube", outcome="PASS", cube_microvms=1, sandbox_id=sb.sandbox_id)
        version = sb.commands.run("opencode --version")
        assert "2.0.24" in version.stdout, "wrong OpenCode version"
        sb.files.write("/workspace/from_provider.txt", "provider-before")
        sb.files.write("/workspace/verify_v2_guest.py", GUEST_CHECK)
        git_gate = "NOT_TESTED"
        if args.require_git:
            sb.files.write("/workspace/README.md", "# Cube OpenCode POC\n")
            steps = (
                "git -C /workspace init -q",
                "git -C /workspace config user.email cube-poc@example.invalid",
                "git -C /workspace config user.name Cube-POC",
                "git -C /workspace add README.md",
                "git -C /workspace commit -qm cube-git-proof",
                "git -C /workspace log -1 --format=%s",
            )
            for step in steps:
                rr = sb.commands.run(step)
                if rr.exit_code != 0:
                    raise RuntimeError("git gate step failed")
            assert "cube-git-proof" in rr.stdout
            git_gate = "PASS"
        password = secrets.token_urlsafe(32)
        command = ("export HOME=/workspace XDG_DATA_HOME=/workspace/.local/share "
                   "XDG_CACHE_HOME=/workspace/.cache XDG_CONFIG_HOME=/workspace/.config; "
                   "cd /workspace; "
                   "OPENCODE_SERVER_PASSWORD=" + shlex.quote(password) +
                   " nohup opencode serve --hostname 0.0.0.0 --port 4096 "
                   ">/workspace/opencode-v2-server.log 2>&1 </dev/null &")
        launched = sb.commands.run(command)
        if launched.exit_code != 0:
            raise RuntimeError("opencode serve background shell exited nonzero")
        guest_cmd = ("AHPOC_PASSWORD=" + shlex.quote(password) +
                     " python3 /workspace/verify_v2_guest.py")
        proof = sb.commands.run(guest_cmd)
        last = next((x for x in reversed(proof.stdout.splitlines()) if x.startswith("{")), "{}")
        data = json.loads(last)
        if proof.exit_code != 0 or data.get("outcome") != "PASS":
            emit(outcome="FAIL", scope="live_cube_opencode2_v2",
                 stage=data.get("stage", "guest_v2"), http_code=data.get("http_code"),
                 exception_type=data.get("exception_type", ""),
                 guest_exit_code=proof.exit_code, v2_server_log_tail="not_exported")
            return 1
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                if sb.files.read("/workspace/from_v2_shell.txt") == "v2-shell-ok":
                    break
            except Exception:
                pass
            time.sleep(0.5)
        else:
            emit(outcome="FAIL", scope="live_cube_opencode2_v2", stage="v2_shell_file_receipt")
            return 1
        second = Sandbox.connect(sb.sandbox_id)
        assert second.files.read("/workspace/from_provider.txt") == "provider-before"

        # Public tools from both SDKs consume the SAME Cube Sandbox lease
        # *after* an OpenCode V2 Shell wrote the file. No hosted LLM calls.
        import asyncio
        from pydantic_ai import Agent
        from pydantic_ai.messages import (ModelResponse, TextPart, ToolCallPart,
                                           ToolReturnPart)
        from pydantic_ai.models.function import FunctionModel
        from agents import function_tool
        from agents.tool_context import ToolContext

        def scripted(messages, _info):
            completed = any(isinstance(part, ToolReturnPart)
                            for msg in messages for part in msg.parts)
            return ModelResponse(parts=[TextPart("pydantic-v2-verified")]) if completed else (
                ModelResponse(parts=[ToolCallPart("read_cube_v2", {})]))

        agent = Agent(FunctionModel(scripted), name="v2-cube-handoff")
        @agent.tool_plain
        def read_cube_v2() -> str:
            """Read the exact authorized Cube Sandbox workspace file."""
            value = second.files.read("/workspace/from_v2_shell.txt")
            assert value == "v2-shell-ok"
            return value

        assert agent.run_sync("verify same Cube workspace").output == "pydantic-v2-verified"

        @function_tool
        def openai_read_cube_v2() -> str:
            """Read the OpenCode-created file from the authorized Cube instance."""
            return second.files.read("/workspace/from_v2_shell.txt")

        argstr = "{}"
        ctx = ToolContext(context={}, tool_name=openai_read_cube_v2.name,
                          tool_call_id="opencode-v2-handoff", tool_arguments=argstr)
        assert (asyncio.run(openai_read_cube_v2.on_invoke_tool(ctx, argstr))
                == "v2-shell-ok")
        emit(outcome="PASS", scope="live_cube_native_opencode2_v2",
             v2_sessions=2, v2_fs_read="PASS", v2_shell_file="PASS",
             cube_native_reconnect="PASS", pydantic_agent_public_tool="PASS",
             openai_public_function_tool="PASS", real_microvms=1,
             model_calls=0, e2b_native="NOT_TESTED", git=git_gate)
        return 0
    except Exception as exc:
        emit(outcome="FAIL", scope="live_cube_opencode2_v2",
             failed_type=type(exc).__name__)
        return 1
    finally:
        if sb is not None:
            try:
                sb.kill()
                emit(stage="cube_kill", outcome="PASS")
            except Exception:
                emit(stage="cube_kill", outcome="FAIL")


if __name__ == "__main__":
    raise SystemExit(main())
