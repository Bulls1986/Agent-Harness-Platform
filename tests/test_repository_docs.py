"""Static documentation contract: links, navigation, actual API coverage, scope."""
from pathlib import Path
import json
import re
import unittest
from copy import deepcopy
from scripts.openapi_signature import contract_signature

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_SOURCE = ROOT / "poc/platform_access/platform_api.py"
INSPECTOR_SOURCE = ROOT / "poc/closed_loop/inspector.py"
LINK = re.compile(r"(?<!!)\[[^]]+\]\(([^)]+)\)")
ROUTE = re.compile(r'@app\.(get|post|put|patch|delete)\("([^"]+)"')


class RepositoryDocumentationTests(unittest.TestCase):
    def test_readme_is_a_usable_open_source_entrypoint(self):
        page=(ROOT/"README.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(page.splitlines()),180)
        for link in ("docs/README.md","docs/guides/QUICKSTART.md",
                     "docs/deployment/README.md","docs/deployment/RELEASE.md",
                     "docs/api/README.md","docs/ARCHITECTURE_VIEWS.md",
                     "LICENSE","docs/ARCHITECTURE_GUARDRAILS.md"):
            self.assertIn(link,page)

    def test_user_facing_navigation_links_resolve(self):
        paths=["README.md","docs/README.md","docs/guides/QUICKSTART.md",
               "docs/guides/USER_GUIDE.md","docs/deployment/README.md",
               "docs/deployment/RELEASE.md","docs/api/README.md",
               "docs/api/PUBLIC_API.md","docs/api/INSPECTOR_API.md"]
        for name in paths:
            file=ROOT/name
            self.assertTrue(file.is_file(),name)
            for target in LINK.findall(file.read_text(encoding="utf-8")):
                if target.startswith(("http://","https://","#","mailto:")):
                    continue
                real=(file.parent/target.split("#")[0]).resolve()
                self.assertTrue(real.exists(),f"{name}: unresolved {target}")

    def test_all_actual_public_routes_are_documented_and_exported(self):
        source=PUBLIC_SOURCE.read_text(encoding="utf-8")
        routes={(method.upper(),route) for method,route in ROUTE.findall(source)
                if route.startswith("/api/v1/")}
        doc=(ROOT/"docs/api/PUBLIC_API.md").read_text(encoding="utf-8")
        schema=json.loads((ROOT/"docs/api/openapi-v1.json").read_text(encoding="utf-8"))
        for method,path in routes:
            with self.subTest(method=method,path=path):
                self.assertIn(path,doc)
                self.assertIn(path,schema["paths"])
                self.assertIn(method.lower(),schema["paths"][path])

    def test_schema_guard_ignores_generator_metadata_but_catches_contract_drift(self):
        schema=json.loads((ROOT/"docs/api/openapi-v1.json").read_text(encoding="utf-8"))
        metadata=deepcopy(schema)
        metadata["info"]["version"]="framework-only-new"
        self.assertEqual(contract_signature(schema),contract_signature(metadata))
        changed=deepcopy(schema)
        changed["paths"].pop("/api/v1/conversations")
        self.assertNotEqual(contract_signature(schema),contract_signature(changed))
        changed=deepcopy(schema)
        changed["components"]["schemas"]["NewTurn"]["properties"].pop("message")
        self.assertNotEqual(contract_signature(schema),contract_signature(changed))

    def test_inspector_is_clearly_separate_and_documented(self):
        source=INSPECTOR_SOURCE.read_text(encoding="utf-8")
        doc=(ROOT/"docs/api/INSPECTOR_API.md").read_text(encoding="utf-8")
        for method,path in ROUTE.findall(source):
            if path.startswith("/api/"):
                with self.subTest(path=path):
                    self.assertIn(path,doc)
        self.assertIn("localhost",doc.lower())
        self.assertIn("NO-GO",(ROOT/"README.md").read_text(encoding="utf-8"))


if __name__=="__main__":
    unittest.main()