"""Milestone-plan regression: a plan is not an implementation claim.

Run locally and in Architecture CI without network, SDK or model credentials.
"""
from pathlib import Path
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PHASES = {
    "DEV-M3": ("dev-m3-run-plan-domain", "run-plan-domain"),
    "DEV-M4": ("dev-m4-reliable-task-facts", "reliable-task-facts"),
    "DEV-M5": ("dev-m5-sandbox-worker-binding", "sandbox-worker-binding"),
    "DEV-M6": ("dev-m6-agent-recipe-execution", "agent-recipe-execution"),
    "DEV-M7": ("dev-m7-platform-access-contract", "platform-access-contract"),
    "DEV-M8": ("dev-m8-external-consumer-integration", "external-consumer-integration"),
    "DEV-M9": ("dev-m9-delivery-readiness", "delivery-readiness"),
}


def validate_milestones(root: Path) -> list[str]:
    errors: list[str] = []
    doc = root / "docs" / "DEVELOPMENT_MILESTONES.md"
    if not doc.is_file():
        return ["missing formal milestone plan"]
    text = doc.read_text(encoding="utf-8")
    for code in [f"DEV-M{i}" for i in range(10)]:
        if code not in text:
            errors.append(f"milestone missing in plan: {code}")
    for code, (change_name, capability) in PHASES.items():
        base = root / "openspec" / "changes" / change_name
        required = [
            ".openspec.yaml", "proposal.md", "design.md", "tasks.md",
            f"specs/{capability}/spec.md",
        ]
        for rel in required:
            if not (base / rel).is_file():
                errors.append(f"{code} missing artifact: {rel}")
        tasks = base / "tasks.md"
        if tasks.is_file():
            body = tasks.read_text(encoding="utf-8")
            if not re.search(r"(?m)^- \[ \] ", body):
                errors.append(f"{code} missing open implementation tasks")
            for line in body.splitlines():
                if not re.match(r"^- \[[xX]\] ", line):
                    continue
                refs = re.findall(
                    r"docs/retrospectives/[A-Za-z0-9_-]+\.md", line
                )
                if not refs or not all((root / ref).is_file() for ref in refs):
                    errors.append(
                        f"{code} incorrectly claims implemented tasks are done "
                        "without locally verifiable evidence"
                    )
        if change_name not in text:
            errors.append(f"{code} missing OpenSpec plan navigation")
    readme = root / "README.md"
    if readme.is_file():
        intro = readme.read_text(encoding="utf-8")[:2500]
        if "正式研发实施" not in intro or "docs/DEVELOPMENT_MILESTONES.md" not in intro:
            errors.append("README lacks formal development stage / plan link")
    return errors


class MilestonePlanTests(unittest.TestCase):
    def test_main_repository_has_seven_independent_openspec_stages(self):
        self.assertEqual(validate_milestones(ROOT), [])

    def test_missing_stage_artifact_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs").mkdir()
            (root / "docs" / "DEVELOPMENT_MILESTONES.md").write_text(
                " ".join(f"DEV-M{i}" for i in range(10)), encoding="utf-8"
            )
            errors = validate_milestones(root)
            self.assertTrue(any("missing artifact" in e for e in errors))

    def test_unearned_task_completion_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs").mkdir()
            content = " ".join(f"DEV-M{i}" for i in range(10)) + " " + " ".join(
                n for n, _ in PHASES.values()
            )
            (root / "docs" / "DEVELOPMENT_MILESTONES.md").write_text(content, encoding="utf-8")
            (root / "README.md").write_text(
                "正式研发实施 docs/DEVELOPMENT_MILESTONES.md", encoding="utf-8"
            )
            for name, cap in PHASES.values():
                base = root / "openspec" / "changes" / name
                for rel in [".openspec.yaml", "proposal.md", "design.md",
                            "tasks.md", f"specs/{cap}/spec.md"]:
                    f = base / rel
                    f.parent.mkdir(parents=True, exist_ok=True)
                    f.write_text("- [ ] work\n", encoding="utf-8")
            victim = root / "openspec/changes/dev-m3-run-plan-domain/tasks.md"
            victim.write_text("- [x] unverified work\n", encoding="utf-8")
            errors = validate_milestones(root)
            self.assertTrue(any("incorrectly claims implemented" in e for e in errors))


    def test_evidenced_task_completion_can_progress(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs" / "retrospectives").mkdir(parents=True)
            (root / "docs/retrospectives/proof.md").write_text(
                "Red/Green/CI evidence", encoding="utf-8"
            )
            content = " ".join(f"DEV-M{i}" for i in range(10)) + " " + " ".join(
                n for n, _ in PHASES.values()
            )
            (root / "docs/DEVELOPMENT_MILESTONES.md").write_text(
                content, encoding="utf-8"
            )
            (root / "README.md").write_text(
                "正式研发实施 docs/DEVELOPMENT_MILESTONES.md", encoding="utf-8"
            )
            for name, cap in PHASES.values():
                base = root / "openspec" / "changes" / name
                for rel in (".openspec.yaml", "proposal.md", "design.md",
                            "tasks.md", f"specs/{cap}/spec.md"):
                    f = base / rel
                    f.parent.mkdir(parents=True, exist_ok=True)
                    f.write_text("- [ ] remaining work\n", encoding="utf-8")
            target = root / "openspec/changes/dev-m3-run-plan-domain/tasks.md"
            target.write_text(
                "- [x] verified slice; **证据**：docs/retrospectives/proof.md\n"
                "- [ ] subsequent live integration\n", encoding="utf-8"
            )
            self.assertEqual(validate_milestones(root), [])



if __name__ == "__main__":
    unittest.main()