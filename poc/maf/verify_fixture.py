"""Independent POC acceptance verifier.

IMPORTANT: `verify_coding` executes candidate Python in a subprocess.
Run untrusted/model-modified candidates **inside a sandbox only**, never inside
a Control Plane process. CI only exercises repository-owned fixed fixtures.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent / "fixtures"

def verify_coding(candidate: Path) -> dict:
    candidate = candidate.resolve()
    if not (candidate / "status.py").is_file():
        return {"scenario": "FIX-CODE-001", "passed": False, "classification": "VERIFICATION_FAILURE", "reason": "missing status.py"}
    env = os.environ.copy()
    env["PYTHONPATH"] = str(candidate)
    cmd = [sys.executable, "-m", "unittest", "discover", "-s",
           str(ROOT / "coding" / "tests"), "-p", "test_status.py"]
    try:
        done = subprocess.run(cmd, env=env, capture_output=True, text=True,
                              timeout=15, check=False, cwd=str(ROOT / "coding" / "tests"))
    except subprocess.TimeoutExpired:
        return {"scenario": "FIX-CODE-001", "passed": False, "classification": "VERIFICATION_FAILURE", "reason": "test timeout"}
    return {"scenario": "FIX-CODE-001", "passed": done.returncode == 0,
            "classification": "SUCCEEDED" if done.returncode == 0 else "VERIFICATION_FAILURE",
            "reason": "unit tests passed" if done.returncode == 0 else "unit tests failed"}

def expected_document() -> dict:
    raw = json.loads((ROOT / "document" / "input.json").read_text(encoding="utf-8"))
    return {"count": len(raw["orders"]),
            "active_count": sum(order["status"] == "active" for order in raw["orders"]),
            "total_amount": sum(order["amount"] for order in raw["orders"])}

def verify_document(candidate: Path) -> dict:
    try:
        actual = json.loads((candidate / "summary.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {"scenario": "FIX-DOC-001", "passed": False,
                "classification": "VERIFICATION_FAILURE", "reason": "missing or invalid summary.json"}
    passed = type(actual) is dict and actual == expected_document()
    return {"scenario": "FIX-DOC-001", "passed": passed,
            "classification": "SUCCEEDED" if passed else "VERIFICATION_FAILURE",
            "reason": "verified against source facts" if passed else "summary mismatch"}

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=["coding", "document"], required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    args = parser.parse_args()
    result = verify_coding(args.candidate) if args.case == "coding" else verify_document(args.candidate)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["passed"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
