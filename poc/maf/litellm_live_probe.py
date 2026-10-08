"""A05/A10: actual LiteLLM OpenAI-compatible MAF HarnessAgent two-turn stream probe.

The credential is read from a short-lived stdin pipe; NEVER passed as CLI
argument, printed, persisted, or included in a response/evidence file.
Run only against explicitly configured internal OpenAI-compatible endpoints.
"""
from __future__ import annotations
import argparse
import asyncio
import json
import sys

from agent_framework import create_harness_agent
from agent_framework.openai import OpenAIChatClient


async def probe(model: str, endpoint: str, key: str) -> dict:
    client=OpenAIChatClient(model=model,base_url=endpoint,api_key=key)
    agent=create_harness_agent(
        client=client,
        name="maf-litellm-live-verification",
        disable_file_memory=True,
        disable_web_search=True,
        disable_tool_auto_approval=True,
        disable_compaction=True,
        # Standard stateless OpenAI-compatible proxies do NOT necessarily
        # implement server-managed Responses session history. Client must
        # explicitly send retained messages on each turn.
        default_options={"store": False, "max_output_tokens": 100},
    )
    session=agent.create_session()
    turns=[]
    prompts=(
        "Keep the reference code ORBIT-742 for this two-turn verification. Reply only ACK.",
        "Which reference code did I provide in the previous message? Reply with the code only.",
    )
    for prompt in prompts:
        pieces=[]
        async def stream_one():
            async for chunk in agent.run(prompt,session=session,stream=True):
                text=getattr(chunk,"text",None)
                if text:
                    pieces.append(text)
        await asyncio.wait_for(stream_one(),timeout=90)
        turns.append("".join(pieces))
    return {
        "model":model,
        "stream_text_received":all(bool(t.strip()) for t in turns),
        "same_native_session":True,
        "recall_verified":"ORBIT-742" in turns[-1],
        "first_turn_chars":len(turns[0]),
        "second_turn_chars":len(turns[-1]),
        "client_managed_history":True,
        "real_model_request":True,
    }


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--model",required=True)
    parser.add_argument("--base-url",required=True)
    args=parser.parse_args()
    # stdin avoids env, shell history, process command line, and saved files.
    credential=sys.stdin.readline().strip()
    if not credential:
        print(json.dumps({"outcome":"SETUP_ERROR","reason":"missing stdin credential"}))
        return 2
    try:
        result=asyncio.run(probe(args.model,args.base_url,credential))
    except Exception as exc:
        # Avoid echoing provider errors: they may contain credential URLs.
        print(json.dumps({"outcome":"RUNTIME_GAP","exception_type":type(exc).__name__}))
        return 1
    result["outcome"]="PASS" if result["stream_text_received"] and result["recall_verified"] else "GAP"
    print(json.dumps(result,sort_keys=True))
    return 0 if result["outcome"]=="PASS" else 1


if __name__=="__main__":
    raise SystemExit(main())
