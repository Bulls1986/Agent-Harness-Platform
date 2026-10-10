"""Read-only Linux CubeSandbox host prerequisite check.

Does not install packages, mount filesystems, alter KVM configuration, pull
images, open network connections, or provision a Cube sandbox.
For WSL2, --backing-path points to the underlying Windows drive mount
containing the distribution's VHDX (e.g. /mnt/e for this POC workstation).
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys

MIN_MEMORY_KIB = 7_500_000
MIN_DISK_BYTES = 50 * 1024**3


def fstype(target: Path) -> str:
    nearest = target
    while not nearest.exists():
        if nearest == nearest.parent:
            return "unknown"
        nearest = nearest.parent
    result = subprocess.run(
        ["findmnt", "-T", str(nearest), "-n", "-o", "FSTYPE"],
        capture_output=True, text=True, timeout=5,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def space(path: Path) -> int | None:
    while not path.exists():
        if path == path.parent:
            return None
        path = path.parent
    return os.statvfs(path).f_bavail * os.statvfs(path).f_frsize


def memory_kib() -> int:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1])
    except (OSError, ValueError, IndexError):
        return 0
    return 0


def kvm_probe() -> dict:
    result = {"device": Path("/dev/kvm").exists(),
              "api_version": None, "create_vm": False}
    if not result["device"]:
        return result
    try:
        fd = os.open("/dev/kvm", os.O_RDWR)
        try:
            result["api_version"] = fcntl.ioctl(fd, 0xAE00, 0)
            vm_fd = fcntl.ioctl(fd, 0xAE01, 0)
            try:
                result["create_vm"] = vm_fd >= 0
            finally:
                os.close(vm_fd)
        finally:
            os.close(fd)
    except OSError:
        pass
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-path", default="/data/cubelet")
    parser.add_argument("--backing-path", default=None,
                        help="physical backing drive, e.g. /mnt/c for Ubuntu WSL2 VHDX")
    args = parser.parse_args()

    if sys.platform != "linux":
        print(json.dumps({"outcome": "BLOCKED", "reason": "Linux host required"}))
        return 2

    target = Path(args.data_path)
    disk = space(target)
    backing = space(Path(args.backing_path)) if args.backing_path else None
    fs = fstype(target)
    kvm = kvm_probe()
    ram = memory_kib()
    controllers = (
        Path("/sys/fs/cgroup/cgroup.controllers").read_text().split()
        if Path("/sys/fs/cgroup/cgroup.controllers").exists()
        else []
    )
    problems = []
    if not kvm["create_vm"]:
        problems.append("KVM_CREATE_VM unavailable")
    if ram < MIN_MEMORY_KIB:
        problems.append("host memory below 8 GB preflight threshold")
    if "cpu" not in controllers:
        problems.append("cgroup v2 cpu controller unavailable")
    if fs != "xfs":
        problems.append("/data/cubelet requires XFS reflink filesystem")
    if disk is None or disk < MIN_DISK_BYTES:
        problems.append("/data/cubelet mount reports less than 50 GiB free")
    if args.backing_path and (backing is None or backing < MIN_DISK_BYTES):
        problems.append("physical WSL backing disk has less than 50 GiB free")

    print(json.dumps({
        "outcome": "PASS_HOST_PREFLIGHT_ONLY" if not problems else "BLOCKED",
        "kvm": kvm,
        "memory_kib": ram,
        "cgroup_cpu": "cpu" in controllers,
        "data_path": str(target),
        "data_fstype": fs,
        "data_free_gib": None if disk is None else round(disk / 1024**3, 1),
        "backing_path": args.backing_path,
        "backing_free_gib": None if backing is None else round(backing / 1024**3, 1),
        "blocking_reasons": problems,
        "cube_microvm_created": False,
        "cube_e2b_live": "NOT_RUN",
        "mutated_host": False,
    }, ensure_ascii=False, sort_keys=True))
    return 2 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
