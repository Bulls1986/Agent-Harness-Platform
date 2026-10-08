"""C11 SandboxProvider SPI: two genuinely isolated Docker execution adapters.

Both adapters use the SAME Docker daemon/isolation backend, not CubeSandbox:
one-shot container vs managed session/exec. This proves an API/adapter switch,
NOT two distinct production sandbox technologies. Host shell/privileged Docker
access belongs only in trusted Worker / Provider adapter, NEVER Workflow.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4
import subprocess
import time


IMAGE="postgres:16-alpine"
PAYLOAD_SIZE=256*1024+16  # controlled 256KiB fixture, not user code


def _docker(*args: str, timeout: int=32) -> str:
    result=subprocess.run(["docker",*args],text=True,capture_output=True,
                          timeout=timeout,check=False)
    if result.returncode:
        # Docker CLI error text may contain sensitive local paths; do not echo.
        raise RuntimeError("Docker sandbox operation failed")
    return result.stdout.strip()


@dataclass(frozen=True)
class SandboxOutput:
    provider: str
    blob: bytes  # inside trusted Data-Plane Activity only; NEVER Workflow!
    image_digest: str
    network_disabled: bool
    read_only_rootfs: bool


class DockerSandboxProvider:
    def __init__(self, mode: str):
        if mode not in ("docker-oneshot","docker-session"):
            raise ValueError("Unsupported C11 provider mode")
        self.mode=mode

    def execute(self) -> SandboxOutput:
        name="poc-c11-"+uuid4().hex[:14]
        # Real isolated container with no network, host volume, devices or
        # capabilities. Data exists on a restricted tmpfs, copied out by
        # privileged trusted Provider after the container completes.
        safe=[
            "--name",name,
            "--network","none",
            "--read-only",
            "--cap-drop","ALL",
            "--security-opt","no-new-privileges",
            "--user","65534:65534",
            "--pids-limit","64",
            "--memory","128m",
            "--cpus","0.5",
            "--tmpfs","/work:rw,nosuid,nodev,mode=1777,size=4194304",
        ]
        script="dd if=/dev/zero of=/work/result.bin bs=1024 count=256 2>/dev/null; printf C11-PAYLOAD-OK!! >> /work/result.bin"
        created=False
        try:
            if self.mode=="docker-oneshot":
                # Keep tmpfs mounted until data is copied out.
                _docker("create",*safe,IMAGE,"sh","-ec",script+"; sleep 120")
                created=True
                _docker("start",name)
                for _ in range(36):
                    probe=subprocess.run(["docker","exec",name,"test","-f",
                                          "/work/result.bin"],capture_output=True,
                                         timeout=4,check=False)
                    if probe.returncode==0: break
                    time.sleep(.2)
                else:
                    raise RuntimeError("Sandbox output never became available")
            else:
                _docker("create",*safe,IMAGE,"sh","-c","sleep 30")
                created=True
                _docker("start",name)
                _docker("exec","--user","65534:65534",name,"sh","-ec",script,timeout=40)
            inspect=_docker("inspect","--format",
                            "{{.HostConfig.NetworkMode}}|{{.HostConfig.ReadonlyRootfs}}",
                            name)
            if inspect!="none|true":
                raise AssertionError("Sandbox did not enforce isolation policy")
            # Docker cp does not expose files stored on container tmpfs on
            # some daemon platforms. Stream directly into trusted Worker
            # memory, never via Temporal History or a host filesystem mount.
            copied=subprocess.run(["docker","exec",name,"cat",
                                   "/work/result.bin"],capture_output=True,
                                  check=False,timeout=24)
            if copied.returncode:
                raise RuntimeError("Sandbox payload stream failed")
            blob=copied.stdout
            if len(blob)!=PAYLOAD_SIZE or not blob.endswith(b"C11-PAYLOAD-OK!!"):
                raise AssertionError("Sandbox produced invalid bounded payload")
            image_id=_docker("image","inspect","--format","{{.Id}}",IMAGE)
            if not image_id.startswith("sha256:"):
                raise AssertionError("Sandbox image fingerprint missing")
            return SandboxOutput(self.mode,blob,image_id,True,True)
        finally:
            if created:
                subprocess.run(["docker","rm","-f",name],capture_output=True,
                               text=True,timeout=20,check=False)
