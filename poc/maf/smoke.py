"""POC-A0: Microsoft Agent Framework HarnessAgent public-API streaming smoke.

Only exercises the vendor runtime. It is NOT a platform Run/Step implementation,
a durable-session test, or evidence that any POC gate has passed.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Mapping
from typing import Any, TextIO


class SmokeConfigurationError(ValueError):
    """Required model/provider configuration is missing."""


def resolve_model(env: Mapping[str, str], cli_model: str | None = None) -> str:
    """Refuse to silently select a particular vendor or model."""
    if not env.get("OPENAI_API_KEY", "").strip():
        raise SmokeConfigurationError("OPENAI_API_KEY is required")
    model = (cli_model or env.get("MAF_POC_MODEL", "")).strip()
    if not model:
        raise SmokeConfigurationError("Set MAF_POC_MODEL or pass --model")
    return model


def create_agent(model: str) -> Any:
    """Use only documented, public MAF Python APIs; import lazily for unit tests."""
    from agent_framework.openai import OpenAIChatClient
    from harness_capabilities import build_harness

    # A05 must not accidentally enable default host file memory, web tools,
    # or automatic tool approval before Sandbox/Approval policies exist.
    return build_harness(OpenAIChatClient(model=model))


async def stream_turn(agent: Any, session: Any, prompt: str, out: TextIO) -> bool:
    """Preserve session identity and stream public chunk.text only."""
    received_text = False
    async for chunk in agent.run(prompt, session=session, stream=True):
        text = getattr(chunk, "text", None)
        if text:
            out.write(text)
            out.flush()
            received_text = True
    out.write("\n")
    return received_text


async def run_smoke(
    agent: Any, prompts: tuple[str, ...], out: TextIO
) -> tuple[bool, ...]:
    """Both turns must use the exact same native MAF session."""
    session = agent.create_session()
    results: list[bool] = []
    for prompt in prompts:
        results.append(await stream_turn(agent, session, prompt, out))
    return tuple(results)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MAF POC-A0 local HarnessAgent smoke")
    parser.add_argument("--model", help="Model/deployment identifier (or MAF_POC_MODEL)")
    parser.add_argument(
        "--prompt",
        default="Create a concise three-step plan for reviewing a code change.",
    )
    parser.add_argument(
        "--follow-up",
        default="Summarize your plan in a single sentence.",
    )
    args = parser.parse_args(argv)
    try:
        model = resolve_model(os.environ, args.model)
        agent = create_agent(model)
        results = asyncio.run(
            run_smoke(agent, (args.prompt, args.follow_up), sys.stdout)
        )
    except (SmokeConfigurationError, ImportError) as exc:
        print(f"SETUP_ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        # Avoid dumping provider request/response or credentials into ordinary logs.
        print(f"RUNTIME_ERROR: {type(exc).__name__}", file=sys.stderr)
        return 1
    if not all(results):
        print("INCONCLUSIVE: at least one turn produced no text chunks", file=sys.stderr)
        return 1
    print("A0 smoke completed; no durable or platform gates claimed", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
