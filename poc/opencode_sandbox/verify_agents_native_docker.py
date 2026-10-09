"""No-model official Agents SDK DockerSandboxClient public API smoke."""

import asyncio
import json
import secrets


async def main():
    try:
        import docker
        from agents.sandbox import Manifest
        from agents.sandbox.sandboxes.docker import (
            DockerSandboxClient, DockerSandboxClientOptions,
        )
    except ImportError:
        print(json.dumps({"outcome": "SKIP", "reason": "openai-agents[docker] unavailable"}))
        return 2

    idempotent_label = "ahp-openai-native-" + secrets.token_hex(5)
    docker_client = docker.from_env()
    provider = DockerSandboxClient(docker_client)
    options = DockerSandboxClientOptions(
        image="postgres:16-alpine", network_mode="none",
        labels={"ahp.poc.native": idempotent_label},
    )
    session = None
    try:
        session = await provider.create(options=options, manifest=Manifest())
        # Official SandboxSession execution API, NOT a host subprocess.
        result = await session.exec("sh", "-c", "echo sdk-native-sandbox", shell=False)
        stdout = str(result.stdout)
        assert result.exit_code == 0 and "sdk-native-sandbox" in stdout, (
            result.exit_code, stdout
        )
        print(json.dumps({
            "outcome": "PASS", "backend": "official_agents_sdk_docker",
            "sdk_native_sandbox_session": True, "network_mode": "none",
            "provider": "DockerSandboxClient", "model_calls": 0,
            "not_proven": ["cross_harness_same_instance", "CubeSandbox", "E2B_live"],
        }, sort_keys=True))
        return 0
    finally:
        if session is not None:
            await session.aclose()
        # Only our uniquely labelled POC containers can be reclaimed.
        for container in docker_client.containers.list(
            all=True, filters={"label": f"ahp.poc.native={idempotent_label}"}
        ):
            container.remove(force=True)
        docker_client.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))