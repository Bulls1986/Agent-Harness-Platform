"""Fail-closed verifier for the observed Agent Harness/Cube POC stack.

Default: local, offline, read-only. No SDK imports, Cube access or model calls.
--profile checks pinned *installed* package versions in the selected venv.
--self-test exercises invalid digest, incompatible SDK, missing evidence and
package version mismatch without installing/uninstalling anything.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from importlib import metadata
import json
from pathlib import Path
import re
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "poc" / "compatibility" / "verified_stack.json"
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
VERSION = re.compile(r"^\d+(?:\.\d+){1,3}(?:[-+._a-zA-Z0-9]*)?$")


def validate(data: dict, *, root: Path = ROOT) -> list[str]:
    """Validate evidence consistency. A future candidate cannot be auto-promoted."""
    errors = []
    if data.get("schema_version") != 1 or not data.get("baseline_id"):
        errors.append("Invalid baseline schema/id")
    if data.get("admission") != "integration_poc_limited_go" or data.get("production_admission") != "no_go":
        errors.append("This manifest must not silently elevate POC to production")
    components = data.get("components", {})
    if not isinstance(components, dict) or not components:
        return ["Missing components"]
    for key, entry in components.items():
        if not VERSION.fullmatch(str(entry.get("version", ""))):
            errors.append("Invalid version for " + key)
        if entry.get("status") not in {"LIVE_PASS", "SDK_RUN_PASS_LOCAL_MODEL", "INSTALLED_CANDIDATE_ONLY"}:
            errors.append("Unknown verification status for " + key)
        evidence = entry.get("evidence", "")
        if not isinstance(evidence, str) or not evidence.startswith(("poc/", "docs/")) or (
            not (root / evidence).is_file()
        ):
            errors.append("Missing or invalid component evidence for " + key)
        if entry.get("type") == "python_sdk" and not entry.get("distribution"):
            errors.append("Missing Python distribution name for " + key)

    failures = data.get("known_incompatible", [])
    if not isinstance(failures, list) or not failures:
        errors.append("Missing incompatible-version evidence")
    else:
        for item in failures:
            key = item.get("component")
            if not key or key not in components:
                errors.append("Incompatible entry has unknown component")
                continue
            # A version may pass with verified DNS/TLS and fail when misconfigured.
            # Only the protocol-level LIVE_FAIL combination is pin-incompatible.
            if (item.get("status") == "LIVE_FAIL"
                    and item.get("version") == components[key].get("version")):
                errors.append("Pinned SDK version is explicitly known incompatible: " + key)
            if not (root / item.get("evidence", "")).is_file():
                errors.append("Missing incompatible-version evidence")
    profiles = data.get("sdk_profiles", {})
    if not isinstance(profiles, dict) or not profiles:
        errors.append("Missing SDK profile matrix")
    else:
        for name, keys in profiles.items():
            if not isinstance(keys, list) or not keys or len(set(keys)) != len(keys):
                errors.append("Invalid SDK profile " + name)
                continue
            for key in keys:
                if key not in components or components[key].get("type") != "python_sdk":
                    errors.append("SDK profile references non-SDK: " + name + "/" + key)

    for combo in data.get("verified_combinations", []):
        if combo.get("status") not in {"LIVE_LIMITED_PASS", "SDK_RUN_PASS_LOCAL_MODEL"}:
            errors.append("Invalid combination evidence status")
        if not combo.get("components") or any(key not in components for key in combo["components"]):
            errors.append("Unknown combination component")
        if not (root / combo.get("evidence", "")).is_file():
            errors.append("Combination evidence missing")
    artifact = data.get("deployment_artifacts", {}).get("opencode_git_cube_guest", {})
    if not SHA256.fullmatch(str(artifact.get("image_digest", ""))):
        errors.append("Missing/malformed immutable OCI manifest digest")
    if artifact.get("template_status") != "READY" or not (
        artifact.get("template_id", "").startswith("tpl-") and artifact.get("template_job_id")
    ):
        errors.append("Cube template not frozen as observed READY")
    artifact_evidence = root / artifact.get("evidence", "")
    if not artifact_evidence.is_file():
        errors.append("Missing OCI/Cube template evidence")
    else:
        txt = artifact_evidence.read_text(encoding="utf-8")
        for key in ("image_digest", "template_id", "template_job_id"):
            if artifact[key] not in txt:
                errors.append("Unsubstantiated OCI/template " + key)
    dockerfile = root / "poc/opencode_sandbox/opencode2_cube_template/Dockerfile"
    if not dockerfile.is_file():
        errors.append("Missing guest Dockerfile")
    else:
        txt = dockerfile.read_text(encoding="utf-8")
        if "ghcr.io/anomalyco/opencode:" + components["opencode2"]["version"] not in txt:
            errors.append("Guest OpenCode version differs from observed baseline")
        if "apt-get install" not in txt or "git" not in txt:
            errors.append("Git guest build step absent")
    if not data.get("rebuild_risks") or not data.get("open_gates"):
        errors.append("POC must carry drift risks and remaining acceptance gates")
    return errors


def check_installed(
    data: dict, profile: str, get_version: Callable[[str], str] = metadata.version
) -> list[str]:
    profiles = data["sdk_profiles"]
    if profile not in profiles:
        return ["Unknown SDK profile: " + profile]
    failures = []
    for component in profiles[profile]:
        spec = data["components"][component]
        distribution = spec["distribution"]
        try:
            actual = get_version(distribution)
        except metadata.PackageNotFoundError:
            failures.append(distribution + " is not installed")
            continue
        if actual != spec["version"]:
            failures.append(distribution + " mismatch: tested " + spec["version"] + ", installed " + actual)
    return failures


def self_test(data: dict) -> None:
    assert not validate(data), "Good manifest must pass"
    for corrupt in (
        lambda x: x["components"]["e2b"].update({"version": "2.53.1"}),
        lambda x: x["deployment_artifacts"]["opencode_git_cube_guest"].update({"image_digest": "sha256:bad"}),
        lambda x: x["components"]["openai_agents"].update({"evidence": "poc/missing-file.md"}),
        lambda x: x.update({"production_admission": "go"}),
        lambda x: x["sdk_profiles"].update({"unsafe": ["not_an_sdk"]}),
    ):
        candidate = deepcopy(data)
        corrupt(candidate)
        assert validate(candidate), "Corrupted baseline must fail closed"
    assert check_installed(data, "cube_e2b_native",
                           lambda name: "2.53.1" if name == "e2b" else "0.23.1")
    assert check_installed(data, "not_a_profile")
    assert not check_installed(data, "runtime_spi_sdk",
                               lambda name: {"pydantic-ai-slim":"2.54.0",
                                             "openai-agents":"0.23.1"}[name])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=[
        "cube_native", "cube_e2b_native", "runtime_spi_sdk",
        "pydantic_harness_candidate",
    ])
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    try:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        errors = validate(data)
        if not errors and args.self_test:
            self_test(data)
        if not errors and args.profile:
            errors = check_installed(data, args.profile)
        print(json.dumps({
            "outcome": "PASS" if not errors else "FAIL",
            "scope": "local_manifest_and_installed_sdk" if args.profile else "offline_manifest_only",
            "baseline_id": data.get("baseline_id"),
            "sdk_profile": args.profile,
            "sdk_versions_verified_in_environment": bool(args.profile and not errors),
            "real_cube_executed": False,
            "production_admission": data.get("production_admission"),
            "self_test": "PASS" if args.self_test and not errors else ("NOT_RUN" if not args.self_test else "FAIL"),
            "errors": errors,
        }, ensure_ascii=False, sort_keys=True), flush=True)
        return 0 if not errors else 1
    except (ValueError, AssertionError, KeyError, TypeError, OSError) as exc:
        print(json.dumps({"outcome":"FAIL", "type":type(exc).__name__,
                          "scope":"baseline_validation_error"},sort_keys=True),flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
