"""Validate only current entrypoint Markdown links, not historical prose URLs."""
from pathlib import Path
import json
import re

root = Path(__file__).resolve().parent.parent
inputs = [
    "README.md",
    "docs/README.md",
    "docs/references/README.md",
    "docs/references/MULTI_HARNESS_TARGET_ARCHITECTURE_20261009.md",
    "docs/references/MULTI_HARNESS_ADMISSION_20261009.md",
    "poc/README.md",
]
bad = []
count = 0
for name in inputs:
    src = root / name
    contents = src.read_text(encoding="utf-8")
    for url in re.findall(r"\[[^\]]+\]\(([^)]+)\)", contents):
        path = url.split("#", 1)[0]
        if not path or ":" in path or path.startswith(("/", "#")):
            continue
        count += 1
        if not (src.parent / path).exists():
            bad.append({"source": name, "target": path})
print(json.dumps({"outcome": "PASS" if not bad else "FAIL", "links_checked": count,
                  "missing_targets": bad}, ensure_ascii=False, sort_keys=True))
raise SystemExit(bool(bad))
