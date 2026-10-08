"""Public MAF API and installed-version probe (no provider credentials required).

Only stable mandatory APIs are asserted. Optional symbols are recorded, never
treated as promises that a provider supports the capability.
"""
from __future__ import annotations
import argparse
import importlib
import importlib.metadata
import inspect
import json
from pathlib import Path

EXPECTED = {
    "agent-framework-core": "1.20.0",
    "agent-framework-openai": "1.15.0",
}
OPTIONAL_SYMBOLS = (
    ("agent_framework", "WorkflowBuilder"),
    ("agent_framework", "CheckpointStorage"),
    ("agent_framework", "ContextProvider"),
    ("agent_framework", "Agent"),
    ("agent_framework", "tool"),
)

def probe() -> dict:
    from agent_framework import create_harness_agent
    from agent_framework.openai import OpenAIChatClient
    versions = {name: importlib.metadata.version(name) for name in EXPECTED}
    signature = inspect.signature(create_harness_agent)
    params = set(signature.parameters)
    # First-party documentation explicitly uses client= in the public factory.
    if "client" not in params:
        raise RuntimeError("MAF public API incompatible: missing client keyword")
    optional = {
        f"{module}.{symbol}": hasattr(importlib.import_module(module), symbol)
        for module, symbol in OPTIONAL_SYMBOLS
    }
    return {
        "versions": versions,
        "versions_match": versions == EXPECTED,
        "harness_factory_parameters": sorted(params),
        "chat_client": f"{OpenAIChatClient.__module__}.{OpenAIChatClient.__name__}",
        "optional_public_symbols": optional,
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = probe()
    serialized = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")
    return 0 if result["versions_match"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
