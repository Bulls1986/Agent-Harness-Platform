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
        archived = False
        if not base.is_dir():
            # Archived milestones remain traceable, while unfinished stages
            # must still have an active OpenSpec with unchecked tasks.
            candidates = sorted(
                (root / "openspec" / "changes" / "archive").glob(
                    f"????-??-??-{change_name}"
                )
            )
            stage = next(
                (line for line in text.splitlines()
                 if line.startswith(f"| {code} ")),
                "",
            )
            if len(candidates) == 1 and "**CLOSED" in stage:
                base, archived = candidates[0], True
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
            if archived:
                if re.search(r"(?m)^- \[ \] ", body):
                    errors.append(f"{code} archived with unfinished tasks")
                official = root / "openspec" / "specs" / capability / "spec.md"
                if not official.is_file():
                    errors.append(f"{code} archived without canonical spec")
                refs = re.findall(r"docs/retrospectives/[A-Za-z0-9_-]+\.md", body)
                if not refs or not all((root / ref).is_file() for ref in refs):
                    errors.append(f"{code} archived without traceable evidence")
            elif not re.search(r"(?m)^- \[ \] ", body):
                errors.append(f"{code} missing open implementation tasks")
            for line in body.splitlines():
                if archived or not re.match(r"^- \[[xX]\] ", line):
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




    def test_archived_m3_requires_closed_plan_canonical_spec_and_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs" / "retrospectives").mkdir(parents=True)
            (root / "docs/retrospectives/proof.md").write_text(
                "official CI proof", encoding="utf-8"
            )
            names = " ".join(n for n, _ in PHASES.values())
            (root / "docs/DEVELOPMENT_MILESTONES.md").write_text(
                " ".join(f"DEV-M{i}" for i in range(10)) + " " + names
                + "\n| DEV-M3 领域内核 | contract | **CLOSED** |",
                encoding="utf-8",
            )
            (root / "README.md").write_text(
                "正式研发实施 docs/DEVELOPMENT_MILESTONES.md",
                encoding="utf-8",
            )
            m3tasks = None
            for code, (name, cap) in PHASES.items():
                base = root / "openspec" / "changes" / name
                if code == "DEV-M3":
                    base = root / "openspec" / "changes" / "archive" / (
                        "2026-10-13-" + name
                    )
                for rel in (".openspec.yaml", "proposal.md", "design.md",
                            "tasks.md", f"specs/{cap}/spec.md"):
                    f = base / rel
                    f.parent.mkdir(parents=True, exist_ok=True)
                    f.write_text("- [ ] remaining work\n", encoding="utf-8")
                if code == "DEV-M3":
                    m3tasks = base / "tasks.md"
            self.assertIsNotNone(m3tasks)
            m3tasks.write_text(
                "- [x] evidence docs/retrospectives/proof.md\n",
                encoding="utf-8",
            )
            official = root / "openspec/specs/run-plan-domain/spec.md"
            official.parent.mkdir(parents=True, exist_ok=True)
            official.write_text("## Requirements\n", encoding="utf-8")
            self.assertEqual(validate_milestones(root), [])

            official.unlink()
            self.assertTrue(any("canonical spec" in error
                                for error in validate_milestones(root)))
            official.write_text("## Requirements\n", encoding="utf-8")
            m3tasks.write_text(
                "- [x] evidence docs/retrospectives/proof.md\n"
                "- [ ] unresolved\n", encoding="utf-8"
            )
            self.assertTrue(any("unfinished tasks" in error
                                for error in validate_milestones(root)))

    def test_m7_archived_bounded_contract_and_api_owner_stay_in_sync(self):
        milestones = (ROOT / "docs/DEVELOPMENT_MILESTONES.md").read_text(encoding="utf-8")
        backlog = (ROOT / "docs/DEVELOPMENT_BACKLOG.md").read_text(encoding="utf-8")
        stage = next(line for line in milestones.splitlines()
                     if line.startswith("| DEV-M7 公共 API/SDK |"))
        owner = next(line for line in backlog.splitlines()
                     if line.startswith("| DEV-API-01 | DEV-M7 |"))
        self.assertIn("**CLOSED（原始平台受控交付限定范围）**", stage)
        self.assertIn("**CLOSED（原始平台受控交付限定范围）**", owner)
        self.assertIn("Production NO-GO", stage)
        self.assertIn("NOT VERIFIED", stage)
        self.assertFalse((ROOT / "openspec/changes/dev-m7-platform-access-contract").exists())
        archive = ROOT / "openspec/changes/archive/2026-10-13-dev-m7-platform-access-contract"
        task_body = (archive / "tasks.md").read_text(encoding="utf-8")
        self.assertNotRegex(task_body, r"(?m)^- \\[ \\] ")
        self.assertEqual(task_body.count("**验收记录**：docs/retrospectives/DEV_M7_FINAL_CLOSEOUT_20261013.md"), 9)
        self.assertTrue((ROOT / "openspec/specs/platform-access-contract/spec.md").is_file())
        report = (ROOT / "docs/retrospectives/DEV_M7_FINAL_CLOSEOUT_20261013.md").read_text(encoding="utf-8")
        for missing in ("NOT VERIFIED", "Gateway/IdP", "OSS", "Approval",
                        "Production NO-GO", "M8", "M9"):
            self.assertIn(missing, report)

    def test_public_api_dependency_points_to_synthetic_consumer_not_reverse(self):
        base = ROOT / "openspec/changes"
        m7 = base / "archive/2026-10-13-dev-m7-platform-access-contract"
        for filename in ("proposal.md", "design.md", "tasks.md"):
            content = (m7 / filename).read_text(encoding="utf-8")
            self.assertNotRegex(content, r"DEV-CONSUMER-0[2-9]\s*前置", filename)
            self.assertIn("DEV-M8" if filename != "tasks.md" else "M8", content)
        m6 = base / "dev-m6-agent-recipe-execution"
        for filename in ("proposal.md", "design.md", "tasks.md"):
            self.assertNotIn("DEV-CONSUMER-04", (m6 / filename).read_text(encoding="utf-8"))
        config = (ROOT / "openspec/config.yaml").read_text(encoding="utf-8")
        self.assertNotIn("外部业务应用-M0", config)

    def test_platform_production_gate_not_private_consumer_acceptance(self):
        stage = ROOT / "openspec/changes/dev-m9-delivery-readiness"
        for filename in ("proposal.md", "design.md", "tasks.md", "specs/delivery-readiness/spec.md"):
            self.assertNotIn("外部业务应用", (stage / filename).read_text(encoding="utf-8"), filename)
        plan = (ROOT / "docs/DEVELOPMENT_MILESTONES.md").read_text(encoding="utf-8")
        self.assertIn("不依赖任何特定业务消费者", plan)



if __name__ == "__main__":
    unittest.main()