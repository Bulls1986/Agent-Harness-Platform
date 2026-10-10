"""Opt-in E2B 2.40.x → real local Cube with *process-private* wildcard DNS.

Cube's systemd-resolved already routes ~cube.app to Cube CoreDNS, but WSL2's
global /etc/resolv.conf points at Windows DNS. Enter a mount namespace and
bind the existing resolver stub *only in the child*; never mutate global DNS,
disable TLS certificate checks, or patch official SDK internals.

Run with CUBE_API_URL/CUBE_TEMPLATE_ID/CUBE_E2B_LIVE_CONFIRM=1, an installed
official E2B SDK (2.40.0), SSL_CERT_FILE trusted CA, and your own key; for a
local Cube auth-disabled demo only, --anonymous-local creates an ephemeral
SDK-format placeholder (never printed).
"""
from __future__ import annotations
import argparse
import importlib.metadata
import os
from pathlib import Path
import secrets
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--anonymous-local", action="store_true")
    parser.add_argument("--openai-native", action="store_true", help="also run the public OpenAI Agents E2BSandboxClient contract")
    parser.add_argument("--in-private-namespace", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.live:
        print("OFFLINE_ONLY: no Sandbox and no system DNS change", flush=True)
        return 0
    if os.environ.get("CUBE_E2B_LIVE_CONFIRM") != "1":
        print("BLOCKED: explicit CUBE_E2B_LIVE_CONFIRM required", flush=True)
        return 2
    api = os.environ.get("E2B_API_URL") or os.environ.get("CUBE_API_URL")
    if api not in ("http://127.0.0.1:3000", "http://localhost:3000"):
        print("BLOCKED: this private DNS POC only supports local Cube API 3000", flush=True)
        return 2
    trusted_ca = os.environ.get("SSL_CERT_FILE", "")
    if not trusted_ca or not Path(trusted_ca).is_file():
        print("BLOCKED: explicit trusted local TLS CA required", flush=True)
        return 2
    if not os.environ.get("CUBE_TEMPLATE_ID"):
        print("BLOCKED: a known READY Cube template is required", flush=True)
        return 2
    if args.anonymous_local and os.environ.get("E2B_API_KEY"):
        print("BLOCKED: cannot combine local anonymous fixture with a configured credential")
        return 2
    if not os.environ.get("E2B_API_KEY") and not args.anonymous_local:
        print("BLOCKED: provide own E2B credential or explicit local anonymous fixture")
        return 2
    if not sys.platform.startswith("linux"):
        print("BLOCKED: only isolated Linux mount namespace supports this demo")
        return 2
    sdk_version = importlib.metadata.version("e2b")
    if sdk_version != "2.40.0":
        print("BLOCKED: only official e2b 2.40.0 verified with this path", flush=True)
        return 2

    if not args.in_private_namespace:
        argv = ["unshare", "-m", "--propagation", "private", sys.executable,
                str(Path(__file__).resolve()), "--live", "--in-private-namespace"]
        if args.anonymous_local:
            argv += ["--anonymous-local"]
        if args.openai_native:
            argv += ["--openai-native"]
        return subprocess.call(argv)

    # --in-private-namespace is an implementation detail, never a way to
    # mount over the host resolver. Fail closed before any mount operation.
    if os.readlink("/proc/self/ns/mnt") == os.readlink("/proc/1/ns/mnt"):
        print("BLOCKED: mount namespace is not isolated; refusing resolver mount")
        return 2
    resolver = "/run/systemd/resolve/stub-resolv.conf"
    if not Path(resolver).exists():
        print("BLOCKED: Cube domain-only systemd-resolved not available")
        return 2
    subprocess.run(["mount", "--bind", resolver, "/etc/resolv.conf"], check=True)
    os.environ["E2B_DOMAIN"] = "cube.app"
    os.environ["E2B_API_URL"] = api
    if args.anonymous_local:
        os.environ["E2B_API_KEY"] = "e2b_" + secrets.token_hex(32)
    # Confirm the systemd-resolved scoped DNS works in THIS process before
    # invoking the official SDK; no global WSL/Windows resolver changes.
    from socket import getaddrinfo
    try:
        ips = sorted({entry[4][0] for entry in getaddrinfo(
            "49983-11111111111111111111111111111111.cube.app", 443)})
    except OSError:
        print("BLOCKED: Cube wildcard DNS resolution failed in private namespace")
        return 2
    print("PRIVATE_CUBE_DNS_OK", ips, "official_e2b", sdk_version, flush=True)
    if args.openai_native:
        from verify_cube_e2b import main as sdk_check
    else:
        from verify_cube_e2b_basic import main as sdk_check
    saved = sys.argv
    try:
        sys.argv = [saved[0], "--live"] + (["--native-sdk"] if args.openai_native else [])
        return sdk_check()
    finally:
        sys.argv = saved


if __name__ == "__main__":
    raise SystemExit(main())
