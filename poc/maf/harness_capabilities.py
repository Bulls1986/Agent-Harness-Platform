"""A06/A07 public harness composition probe: intentionally no model calls.

Native Todo/Mode are context providers, NOT platform-owned Plan/Step/Run facts.
No implicit host filesystem, shell, web search or tool auto-approval.
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Any

from agent_framework import ContextProvider, create_harness_agent
from agent_framework.openai import OpenAIChatClient


class FixedTaskContext(ContextProvider):
    """Demonstrates public context hooks; caller controls instructions, not agent."""

    def __init__(self, note: str = "Use only externally verified completion facts.") -> None:
        super().__init__("poc-task-context")
        self.note = note

    async def before_run(
        self, *, agent: Any, session: Any, context: Any, state: dict[str, Any]
    ) -> None:
        context.extend_instructions(self.source_id, self.note)
        state["before_count"] = int(state.get("before_count", 0)) + 1

    async def after_run(
        self, *, agent: Any, session: Any, context: Any, state: dict[str, Any]
    ) -> None:
        state["after_count"] = int(state.get("after_count", 0)) + 1


def build_harness(client: Any, provider: ContextProvider | None = None) -> Any:
    return create_harness_agent(
        client=client,
        name="maf-public-extensions-poc",
        context_providers=[provider or FixedTaskContext()],
        disable_file_memory=True,
        disable_web_search=True,
        disable_tool_auto_approval=True,
        disable_compaction=True,  # A07 compaction needs a separately measured probe
    )


def inspect_harness(agent: Any) -> dict[str, Any]:
    providers = tuple(type(provider).__name__ for provider in agent.context_providers)
    session = agent.create_session()
    if not hasattr(session, "to_dict"):
        raise RuntimeError("Native AgentSession public serialization unavailable")
    session_payload = session.to_dict()
    if not isinstance(session_payload, dict):
        raise RuntimeError("AgentSession serialization is not a dict")
    return {
        "providers": list(providers),
        "native_todo": "TodoProvider" in providers,
        "native_mode": "AgentModeProvider" in providers,
        "custom_context": "FixedTaskContext" in providers,
        "file_memory_disabled": "FileMemoryProvider" not in providers,
        "session_serializable": True,
        "durable_session_verified": False,
        "compaction_verified": False,
        "plan_domain_mapping_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="A06/A07 offline composition probe")
    parser.add_argument("--model", default="ci-no-network-model")
    args = parser.parse_args()
    # Dummy key is used only to build client; this command NEVER calls a model.
    os.environ.setdefault("OPENAI_API_KEY", "ci-placeholder-not-a-secret")
    client = OpenAIChatClient(model=args.model)
    result = inspect_harness(build_harness(client))
    print(json.dumps(result, sort_keys=True))
    return 0 if all(
        result[field] for field in
        ("native_todo", "native_mode", "custom_context",
         "file_memory_disabled", "session_serializable")
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
