"""Live-provider A05 probe: checks real streaming *and* two-turn session recall.

Unlike A00, text in both responses alone is insufficient: the second turn must
recall a random marker only given in the first turn. No plaintext credentials
or raw model content are written to a report.
"""
from __future__ import annotations
import argparse
import asyncio
import io
import json
import os
import secrets
import sys
from collections.abc import Mapping
from typing import Any

from smoke import SmokeConfigurationError, create_agent, resolve_model, run_smoke

async def probe_agent(agent: Any, marker: str) -> dict:
    output = io.StringIO()
    prompts = (
        f"Remember this marker for the next turn: {marker}. Reply ACK only.",
        "What exact marker did I ask you to remember? Reply only that marker.",
    )
    chunks = await run_smoke(agent, prompts, output)
    lines = output.getvalue().splitlines()
    return {
        "streamed_both_turns": len(chunks) == 2 and all(chunks),
        "recalled_marker": len(lines) == 2 and marker in lines[1],
        "turn_count": len(chunks),
    }

def probe_status(results: Mapping[str, Any]) -> bool:
    return bool(results.get("streamed_both_turns") and results.get("recalled_marker"))

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Real-provider A05 continuity probe")
    parser.add_argument("--model", default=None)
    args = parser.parse_args(argv)
    try:
        model = resolve_model(os.environ, args.model)
        agent = create_agent(model)
        marker = f"MAF_POC_{secrets.token_hex(10)}"
        result = asyncio.run(probe_agent(agent, marker))
    except (SmokeConfigurationError, ImportError) as exc:
        print(f"SETUP_ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"RUNTIME_ERROR: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(json.dumps({"scenario": "A05", **result, "passed": probe_status(result)}))
    return 0 if probe_status(result) else 1

if __name__ == "__main__":
    raise SystemExit(main())
