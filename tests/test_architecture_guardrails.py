"""Offline regression tests for deterministic architecture-guard script."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_architecture_guardrails import REQUIRED, VIEW_NAMES, check_repository, check_vendor_imports, check_views


def fixture(root: Path) -> None:
    for item in REQUIRED:
        p = root / item
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("fixture", encoding="utf-8")
    fence = chr(96) * 3
    doc = "### 3.1 八类分层架构视图\n"
    for i, name in enumerate(VIEW_NAMES, 1):
        doc += f"#### 3.1.{i} {name}\n"
        if i == 8:
            doc += "##### 3.1.8.1 正常\n"
        doc += f"{fence}mermaid\nflowchart TB\n  A --> B\n{fence}\n"
        if i == 8:
            doc += "##### 3.1.8.2 恢复\n"
            doc += f"{fence}mermaid\nsequenceDiagram\n  A->>B: hello\n{fence}\n"
    (root / "README.md").write_text("ARCHITECTURE_GUARDRAILS.md\n" + doc + "## 4. 为什么采用这样的技术方案？", encoding="utf-8")
    (root / "AGENTS.md").write_text("ARCHITECTURE_GUARDRAILS.md", encoding="utf-8")
    (root / "docs/ARCHITECTURE_VIEWS.md").write_text("README.md#31-八类分层架构视图", encoding="utf-8")
    (root / "poc/runtime_spi/contract.py").write_text("from dataclasses import dataclass\n", encoding="utf-8")


class GuardTests(unittest.TestCase):
    def test_valid_fixture(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fixture(root)
            self.assertEqual(check_repository(root), [])

    def test_banned_vendor_imports(self):
        issues = check_vendor_imports("from agents import Runner\nimport pydantic_ai\n", "contract.py")
        self.assertEqual(len(issues), 2)

    def test_hatchet_and_rejected_dbos_are_forbidden_in_platform_domain(self):
        issues = check_vendor_imports("from hatchet_sdk import Hatchet\nfrom dbos import DBOS\n", "contract.py")
        self.assertEqual(len(issues), 2)

    def test_relative_contract_import_allowed(self):
        self.assertEqual(check_vendor_imports("from .contract import RunRequest\n", "contract.py"), [])

    def test_missing_diagram_detected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fixture(root)
            readme = (root / "README.md").read_text(encoding="utf-8")
            first = chr(96) * 3 + "mermaid"
            readme = readme.replace(first, "~~~text", 1)
            self.assertTrue(any("expected 9 Mermaid" in x for x in check_views(
                readme, "README.md#31-八类分层架构视图")))

    def test_duplicate_legacy_diagram_detected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fixture(root)
            readme = (root / "README.md").read_text(encoding="utf-8")
            legacy = "README.md#31-八类分层架构视图\n" + chr(96)*3 + "mermaid\nflowchart LR\nA-->B\n" + chr(96)*3
            self.assertTrue(any("duplicates" in x for x in check_views(readme, legacy)))

    def test_missing_contract_detected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fixture(root)
            (root / "docs/POC.md").unlink()
            self.assertTrue(any("required file missing" in x for x in check_repository(root)))

    def test_vendor_import_in_platform_contract_detected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fixture(root)
            (root / "poc/runtime_spi/contract.py").write_text("from agents import Runner", encoding="utf-8")
            self.assertTrue(any("G03/G04" in x for x in check_repository(root)))


if __name__ == "__main__":
    unittest.main()