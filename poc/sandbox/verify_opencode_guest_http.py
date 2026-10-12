"""Native Cube Guest OpenCode *public HTTP API* smoke (no fake agent tools).

This does not exercise an LLM. It checks the real standalone OpenCode binary,
starts its authenticated API **inside** a short-lived real Cube MicroVM,
creates an actual OpenCode Session and checks its public shell endpoint. No
shell, Git or OpenCode binary is ever launched on the platform Host.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import shlex
import time
from urllib.parse import parse_qs, quote, urlsplit
from uuid import uuid4


def resolve_api_prefix(version: str) -> str:
    """OpenCode v2 changed its external API namespace; do not guess routes."""
    if not isinstance(version, str):
        raise ValueError("Unknown OpenCode API version")
    match = re.fullmatch(r"(?:opencode )?v?([12])\.\d+\.\d+", version.strip())
    if match is None:
        raise ValueError("Unknown OpenCode API version")
    return "/api" if match.group(1) == "2" else ""


def native_session_id(response: object, prefix: str) -> str:
    """Unwrap exact public native response, never trust a caller-supplied ID."""
    if not isinstance(response, dict):
        raise ValueError("OpenCode did not return a Session response")
    if prefix == "/api":
        if "id" in response or not isinstance(response.get("data"), dict):
            raise ValueError("OpenCode v2 Session envelope missing/ambiguous")
        session = response["data"]
    elif prefix == "":
        if "data" in response:
            raise ValueError("OpenCode v1 Session envelope invalid")
        session = response
    else:
        raise ValueError("Unknown OpenCode public API namespace")
    ident = session.get("id")
    if not isinstance(ident, str) or not re.fullmatch(r"[A-Za-z0-9_-]{3,128}", ident):
        raise ValueError("Untrusted OpenCode Session identifier")
    return ident


def _safe_server_command() -> str:
    return (
        "sh -lc 'mkdir -p /workspace/m5-opencode && "
        "git init -q /workspace/m5-opencode && "
        "cd /workspace/m5-opencode && "
        "nohup opencode serve --hostname 127.0.0.1 --port 4096 "
        ">/tmp/ahp-m5-opencode-serve.log 2>&1 </dev/null & "
        "echo NATIVE_SERVE_START_REQUESTED'"
    )


def _guest_http(sandbox, password: str, method: str, path: str,
                json_body: str | None = None):
    if method not in ("GET", "POST") or not isinstance(path, str):
        raise ValueError("Only fixed OpenCode API routes")
    url = urlsplit(path)
    simple_route = re.fullmatch(r"/[a-zA-Z0-9_/-]+", url.path)
    v2_file_route = re.fullmatch(
        r"/api/fs/read/[a-zA-Z0-9_-]+(?:\.[a-zA-Z0-9_-]+)+", url.path)
    if (url.scheme or url.netloc or url.fragment
            or not (simple_route or v2_file_route)):
        raise ValueError("Untrusted OpenCode URI")
    if url.query:
        if method != "GET" or not url.path.endswith("/file/content"):
            raise ValueError("Only canonical Guest file content query is supported")
        params = parse_qs(url.query, strict_parsing=True)
        if list(params) != ["path"] or len(params["path"]) != 1:
            raise ValueError("Ambiguous native file path")
        file_path = params["path"][0]
        if (not file_path.startswith("/workspace/")
                or "//" in file_path or chr(92) in file_path
                or any(segment in ("", ".", "..")
                       for segment in file_path[len("/workspace/"):].split("/"))
                or url.query != "path=" + quote(file_path, safe="")):
            raise ValueError("Native file path not canonical workspace-only")
    # Guest-local client, not host curl and never a URL or command supplied by
    # the browser. Inject the secret in the Guest process env, not command argv.
    command = (
        "curl --silent --show-error --max-time 12 "
        "--fail-with-body -u opencode:\"$OPENCODE_SERVER_PASSWORD\" "
        "-H 'Content-Type: application/json' "
    )
    if method == "POST":
        if json_body is not None:
            json.loads(json_body)
        command += "-X POST -d " + shlex.quote(json_body or "{}") + " "
    command += shlex.quote("http://127.0.0.1:4096" + path)
    response = sandbox.commands.run(
        "sh -c " + shlex.quote(command), timeout=18,
        envs={"OPENCODE_SERVER_PASSWORD": password},
    )
    if response.exit_code != 0:
        raise RuntimeError("Real Guest OpenCode HTTP request failed")
    if method == "GET" and path.startswith("/api/fs/read/"):
        # OpenCode v2 public filesystem is a binary/stream API, not JSON.
        # This synthetic verifier reads one UTF-8 test file only.
        return response.stdout
    if not response.stdout.strip():
        if method == "POST" and path.endswith("/shell"):
            # V2 may report an asynchronous/empty tool envelope; only the
            # actual Guest file effect can confirm successful execution.
            return None
        raise RuntimeError("Native Session API returned an empty body")
    return json.loads(response.stdout)


def main() -> int:
    if not all(os.environ.get(k) for k in ("CUBE_API_URL", "CUBE_TEMPLATE_ID")):
        raise RuntimeError("REAL_OPENCODE_HTTP_GATE_NOT_RUN")
    from cubesandbox import Sandbox
    sandbox = None
    secret = secrets.token_urlsafe(36)
    outcome = None
    try:
        sandbox = Sandbox.create(
            template=os.environ["CUBE_TEMPLATE_ID"], timeout=240,
            allow_internet_access=False,
            metadata={"purpose": "synthetic-opencode-http",
                      "probe": uuid4().hex},
        )
        started = sandbox.commands.run(
            _safe_server_command(), timeout=20,
            envs={"OPENCODE_SERVER_PASSWORD": secret},
        )
        if started.exit_code != 0:
            raise RuntimeError("OpenCode serve could not start in Cube Guest")
        version_result = sandbox.commands.run("opencode --version", timeout=12)
        print("NATIVE_OPENCODE_VERSION",
              version_result.stdout.strip()[:90], flush=True)
        api_prefix = resolve_api_prefix(version_result.stdout.strip())
        last_error = None
        for _ in range(7):
            time.sleep(1)
            try:
                health = _guest_http(
                    sandbox, secret, "GET", api_prefix + "/session")
            except Exception as exc:
                last_error = type(exc).__name__
                continue
            if isinstance(health, (list, dict)):
                break
        else:
            info = sandbox.commands.run(
                "sh -lc 'command -v curl; ps -ef | grep [o]pencode | head -3; "
                "tail -c 900 /tmp/ahp-m5-opencode-serve.log 2>/dev/null || true'",
                timeout=12,
            )
            # Only static synthetic bootstrap output and no bearer secrets
            # are allowed into test diagnostics.
            print("GUEST_BOOTSTRAP_DIAGNOSTIC",
                  (info.stdout or "").replace(secret, "[REDACTED]")[:1000],
                  "last_client_error", last_error, flush=True)
            raise RuntimeError("OpenCode authenticated Guest API not healthy")
        created = _guest_http(
            sandbox, secret, "POST", api_prefix + "/session")
        if not isinstance(created, dict):
            raise RuntimeError("OpenCode native Session creation returned non-object")
        print("OPENCODE_CREATED_ENVELOPE_KEYS",
              sorted(created)[:20], flush=True)
        session_id = native_session_id(created, api_prefix)
        # The request is a fixed synthetic command using OpenCode's *public
        # Session Shell* API; never a host subprocess or SDK raw command
        # pretending to be an OpenCode Tool execution.
        native_shell = _guest_http(
            sandbox, secret, "POST",
            api_prefix + "/session/" + session_id + "/shell",
            json.dumps({
                "agent": "build",
                "command": (
                    "printf native-opencode-shell-evidence > "
                    "/workspace/m5-opencode/native-tool.txt && "
                    "git init -q /workspace/m5-opencode"
                ),
            }),
        )
        print("NATIVE_OPENCODE_SHELL_RESULT_TYPE",
              type(native_shell).__name__, flush=True)
        guest_content = None
        for _ in range(8):
            try:
                guest_content = sandbox.files.read(
                    "/workspace/m5-opencode/native-tool.txt")
                break
            except Exception:
                time.sleep(1)
        if guest_content != "native-opencode-shell-evidence":
            raise RuntimeError("OpenCode native Shell did not write actual Guest data")
        # OpenCode public Files API (not Cube File API) must return the
        # exact native Shell effect. v2 uses an encoded workspace path.
        if api_prefix == "/api":
            file_api = _guest_http(
                sandbox, secret, "GET",
                "/api/fs/read/native-tool.txt",
            )
            file_content = file_api
        else:
            file_api = _guest_http(
                sandbox, secret, "GET",
                "/file/content?path=" +
                quote("/workspace/m5-opencode/native-tool.txt", safe=""),
            )
            file_data = file_api.get("data") if isinstance(file_api, dict) else None
            file_content = file_data.get("content") if isinstance(file_data, dict) else None
        if not isinstance(file_content, str) or file_content.strip() != "native-opencode-shell-evidence":
            raise RuntimeError("OpenCode native Files API returned wrong Guest bytes")
        git_api = _guest_http(sandbox, secret, "GET", api_prefix + "/vcs")
        if (not isinstance(git_api, dict)
                or not isinstance(git_api.get("data"), dict)):
            raise RuntimeError("OpenCode native Git/VCS API returned no repo data")
        outcome = {"outcome": "PASS_REAL_CUBE_GUEST_OPENCODE_SESSION_HTTP",
                   "sandbox_id": sandbox.sandbox_id,
                   "opencode_version": version_result.stdout.strip()[:80],
                   "native_session_id": session_id,
                   "session_created_inside_real_guest": True,
                   "native_session_shell_guest_effect": True,
                   "opencode_files_native_read_verified": True,
                   "opencode_git_vcs_native_api_verified": True}
        print(json.dumps(outcome, sort_keys=True), flush=True)
    finally:
        if sandbox is not None:
            sandbox.kill()
            print("NATIVE_OPENCODE_HTTP_GUEST_DESTROY_ACK", flush=True)
    return 0 if outcome else 2


if __name__ == "__main__":
    raise SystemExit(main())
