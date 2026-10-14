#!/usr/bin/env python3
"""Narrow architecture checks: docs + direct platform SPI imports, not semantic proof."""
from __future__ import annotations
import ast
from pathlib import Path
import re
import sys

REQUIRED = (
    "README.md", "AGENTS.md", "docs/ARCHITECTURE.md",
    "docs/ARCHITECTURE_BACKLOG.md", "docs/POC.md",
    "docs/ARCHITECTURE_GUARDRAILS.md", "docs/ARCHITECTURE_VIEWS.md",
    "docs/references/HATCHET_PROCESS_DURABLE_ARCHITECTURE_20261010.md",
    ".github/PULL_REQUEST_TEMPLATE.md", ".github/workflows/architecture-guard.yml",
    "poc/runtime_spi/contract.py",
    "docs/references/HATCHET_WORKFLOW_MAPPING_CONTRACT_20261010.md",
    "docs/references/HARNESS_HATCHET_CONSISTENCY_CONTRACT_20261010.md",
    "docs/references/HATCHET_WORKER_SANDBOX_BINDING_CONTRACT_20261010.md",
    "docs/DEVELOPMENT_BACKLOG.md",
    "docs/references/DOMAIN_MODEL_AND_STATE_CONTRACT.md",
    "docs/references/FAILURE_IDEMPOTENCY_AND_RECOVERY.md",
    "docs/references/EXECUTION_LEASE_FENCING_HEARTBEAT.md",
    "docs/references/TASK_RECOVERY_COVERAGE_AND_SEMANTICS.md",
    "docs/references/IDENTITY_AND_AUTHORIZATION_PROPAGATION.md",
    "docs/references/REGISTRY_AND_VERSIONING.md",
)
# Scope intentionally only current platform-owned contract.py, not SDK adapters.
VENDOR_ROOTS = frozenset({"agents", "openai", "pydantic", "pydantic_ai",
                          "opencode", "cubesandbox", "e2b", "temporalio",
                          "azure", "microsoft", "hatchet_sdk", "dbos", "sqlalchemy",
                          "psycopg", "psycopg2", "asyncpg"})
VIEW_NAMES = ("业务架构", "逻辑架构", "应用架构", "技术架构",
              "数据架构", "部署架构", "功能架构", "运行架构")
FENCE = re.compile(r"^" + chr(96) * 3 + r"mermaid[ \t]*\r?\n(.*?)^" +
                   chr(96) * 3 + r"[ \t]*$", re.M | re.S)


def check_vendor_imports(source: str, label: str) -> list[str]:
    try:
        tree = ast.parse(source, filename=label)
    except SyntaxError as exc:
        return [f"{label}: invalid Python syntax: {exc}"]
    issues = []
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            names = [node.module]
        for name in names:
            if name.split(".")[0] in VENDOR_ROOTS:
                issues.append(f"{label}:{node.lineno}: G03/G04 SDK/Provider import {name!r} belongs in an Adapter")
    return issues


def check_views(readme: str, views: str) -> list[str]:
    """One canonical diagram source in docs, short README links to it."""
    issues = []
    if "docs/ARCHITECTURE_VIEWS.md" not in readme:
        issues.append("README: link to canonical architecture views missing")
    start=views.find("### 3.1 八类分层架构视图")
    if start<0:
        return issues+["ARCHITECTURE_VIEWS: missing section 3.1"]
    section=views[start:]
    for n,name in enumerate(VIEW_NAMES,1):
        if f"#### 3.1.{n} {name}" not in section:
            issues.append(f"ARCHITECTURE_VIEWS: missing 3.1.{n} {name}")
    if not all(f"##### 3.1.8.{i} " in section for i in (1,2)):
        issues.append("ARCHITECTURE_VIEWS: missing two runtime execution/recovery diagrams")
    diagrams=FENCE.findall(section)
    if len(diagrams)!=9:
        issues.append(f"ARCHITECTURE_VIEWS: expected 9 Mermaid diagrams; found {len(diagrams)}")
    for i,diagram in enumerate(diagrams,1):
        if not diagram.lstrip().startswith(("flowchart ","sequenceDiagram")):
            issues.append(f"ARCHITECTURE_VIEWS: unsupported Mermaid diagram {i} start")
    # A small README explainer is acceptable; copying the 9 canonical views is not.
    if "#### 3.1.1 业务架构" in readme or len(FENCE.findall(readme))>=9:
        issues.append("README duplicates canonical architecture views")
    if "README.md#31-" in views:
        issues.append("ARCHITECTURE_VIEWS still points back to legacy README")
    return issues


def check_repository(root: Path) -> list[str]:
    missing = [f"required file missing: {item}" for item in REQUIRED if not (root / item).is_file()]
    if missing:
        return missing
    readme = (root / "README.md").read_text(encoding="utf-8")
    legacy = (root / "docs/ARCHITECTURE_VIEWS.md").read_text(encoding="utf-8")
    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    issues = []
    if "ARCHITECTURE_GUARDRAILS.md" not in readme:
        issues.append("README: guardrails entrypoint missing")
    if "ARCHITECTURE_GUARDRAILS.md" not in agents:
        issues.append("AGENTS: mandatory guardrails link missing")
    issues.extend(check_views(readme, legacy))
    issues.extend(check_vendor_imports(
        (root / "poc/runtime_spi/contract.py").read_text(encoding="utf-8"),
        "poc/runtime_spi/contract.py"))
    return issues


def main() -> int:
    issues = check_repository(Path(__file__).resolve().parents[1])
    for issue in issues:
        print("ARCHITECTURE GUARD FAIL:", issue)
    if issues:
        return 1
    print("ARCHITECTURE GUARD PASS: 8 views / 9 Mermaid diagrams, contracts, SPI import boundary")
    print("Warning: dynamic imports, behavioral correctness and production safety require separate tests/review.")
    return 0


if __name__ == "__main__":
    sys.exit(main())