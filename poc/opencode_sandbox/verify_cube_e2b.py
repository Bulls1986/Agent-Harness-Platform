"""CubeSandbox E2B SDK contract suite. No local-Docker fake Cube.

No args: offline SDK/API/configuration preflight, does not create a sandbox.
--live: real Cube API + envd commands/files/isolated instances + optional
         OpenAI Agents SDK E2BSandboxClient native API.

The probe NEVER calls a model, prints keys, or auto-creates persistent volumes.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import inspect
import json
import os
import secrets
from urllib.parse import urlparse


def report(**data):
    print(json.dumps(data, ensure_ascii=False, sort_keys=True))


def configuration():
    url = os.environ.get("E2B_API_URL") or os.environ.get("CUBE_API_URL") or ""
    template = os.environ.get("CUBE_TEMPLATE_ID") or ""
    key = os.environ.get("E2B_API_KEY") or os.environ.get("CUBE_API_KEY") or ""
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http") or not parsed.hostname:
        return None, "Cube E2B API URL is not configured"
    if parsed.hostname in ("api.e2b.dev", "e2b.dev", "api.e2b.app"):
        return None, "E2B Cloud URL is not a Cube endpoint"
    if not template:
        return None, "CUBE_TEMPLATE_ID is not configured"
    if not key:
        return None, "E2B_API_KEY or CUBE_API_KEY is not configured"
    if parsed.scheme == "http" and parsed.hostname not in (
        "127.0.0.1", "localhost", "::1"
    ) and os.environ.get("CUBE_ALLOW_PRIVATE_HTTP") != "1":
        return None, "Unencrypted non-loopback Cube endpoint not explicitly allowed"
    return {"url": url, "template": template, "key": key}, None


def sdk_surface():
    from e2b import Sandbox
    from agents.extensions.sandbox import (
        E2BSandboxClient, E2BSandboxClientOptions, E2BSandboxType,
    )
    from agents.sandbox import Manifest

    signatures = {
        "e2b_create_template": "template" in inspect.signature(Sandbox.create).parameters,
        "e2b_commands_run": hasattr(Sandbox, "commands"),
        "openai_native_e2b_create":
            "options" in inspect.signature(E2BSandboxClient.create).parameters,
        "openai_native_e2b_options_template":
            "template" in inspect.signature(E2BSandboxClientOptions).parameters,
        "openai_e2b_type": E2BSandboxType.E2B is not None,
        "manifest": Manifest is not None,
    }
    # Sandbox.commands is an instance property, not necessarily on class.
    signatures["e2b_commands_run"] = "commands" in inspect.get_annotations(Sandbox) or (
        hasattr(Sandbox, "commands")
    )
    signatures["e2b_files"] = hasattr(Sandbox, "files")
    return signatures


def base_e2b_run(config):
    from e2b import Sandbox

    os.environ["E2B_API_URL"] = config["url"]
    os.environ["E2B_API_KEY"] = config["key"]
    alpha = beta = None
    sample = "ahp_e2b_" + secrets.token_hex(8) + ".txt"
    path = "/workspace/" + sample
    try:
        alpha = Sandbox.create(template=config["template"], timeout=120)
        alpha.files.write(path, "cube-e2b-alpha")
        value = alpha.files.read(path)
        if value != "cube-e2b-alpha":
            raise AssertionError("Cube E2B FS roundtrip mismatch")
        result = alpha.commands.run("cat " + path)
        if "cube-e2b-alpha" not in result.stdout:
            raise AssertionError("Cube E2B commands.run mismatch")

        beta = Sandbox.create(template=config["template"], timeout=120)
        beta.files.write(path, "cube-e2b-beta")
        if beta.files.read(path) != "cube-e2b-beta":
            raise AssertionError("Cube E2B second sandbox write mismatch")
        if alpha.files.read(path) != "cube-e2b-alpha":
            raise AssertionError("Different Cube sandbox contents leaked")
        return {"official_e2b_sdk": "PASS", "sandbox_instances": 2,
                "files_write_read": "PASS", "commands_run": "PASS",
                "cross_instance_content_isolation": "PASS"}
    finally:
        for sbx in (beta, alpha):
            if sbx is not None:
                sbx.kill()


async def sdk_client_run(config):
    from agents.extensions.sandbox import (
        E2BSandboxClient, E2BSandboxClientOptions, E2BSandboxType,
    )
    from agents.sandbox import Manifest

    os.environ["E2B_API_URL"] = config["url"]
    os.environ["E2B_API_KEY"] = config["key"]
    client = E2BSandboxClient()
    session = None
    try:
        session = await client.create(
            options=E2BSandboxClientOptions(
                template=config["template"], sandbox_type=E2BSandboxType.E2B,
                timeout=120,
            ),
            manifest=Manifest(),
        )
        result = await session.exec("sh", "-c", "printf sdk-native-cube")
        if result.exit_code != 0 or "sdk-native-cube" not in str(result.stdout):
            raise AssertionError("OpenAI native E2B exec did not produce expected output")
        return {"openai_agents_e2b_client": "PASS", "sdk_private_patches": False}
    finally:
        if session is not None:
            await session.aclose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--native-sdk", action="store_true",
                        help="also run official OpenAI Agents E2BSandboxClient")
    args = parser.parse_args()

    config, missing = configuration()
    try:
        from e2b import Sandbox
        from agents.extensions.sandbox import E2BSandboxClient
    except ImportError:
        report(outcome="SKIP", reason="install e2b==2.53.1 and openai-agents==0.23.1")
        return 2

    versions = {
        "e2b": importlib.metadata.version("e2b"),
        "openai_agents": importlib.metadata.version("openai-agents"),
    }
    surface = sdk_surface()
    try:
        from cubesandbox import Sandbox as CubeNativeSandbox
        versions["cubesandbox"] = importlib.metadata.version("cubesandbox")
        surface["cube_native_create"] = (
            "template" in inspect.signature(CubeNativeSandbox.create).parameters
        )
    except ImportError:
        surface["cube_native_create"] = False
    if not args.live:
        report(outcome="PASS", scope="offline_sdk_surface_only",
               live_cube="NOT_RUN", sdk_versions=versions,
               cube_endpoint_configured=bool(config),
               blocking_reason=missing, surfaces=surface)
        return 0
    if missing:
        report(outcome="BLOCKED", scope="live_cube", reason=missing)
        return 2
    if os.environ.get("CUBE_E2B_LIVE_CONFIRM") != "1":
        report(outcome="BLOCKED", scope="live_cube",
               reason="explicit CUBE_E2B_LIVE_CONFIRM=1 required")
        return 2

    try:
        result = base_e2b_run(config)
        if args.native_sdk:
            result.update(asyncio.run(sdk_client_run(config)))
        report(outcome="PASS", scope="live_cube", sdk_versions=versions,
               model_calls=0, **result)
        return 0
    except Exception as exc:
        # Avoid printing SDK exception strings: they may include endpoints,
        # request headers, tokens, or sensitive server content.
        report(outcome="FAIL", scope="live_cube", failed_type=type(exc).__name__,
               sdk_versions=versions, model_calls=0)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
