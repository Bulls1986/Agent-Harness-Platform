"""C09 real Agent Runtime adapters. OpenAI-compatible model behind LiteLLM.

Two genuinely different public Agent SDKs, not two models or two names of
the same client. Only this Activity/data-plane module imports the SDKs.
No shell, file memory, browsing, tool permissions, tracing or compaction.
Never include raw model text, API keys, URLs or native provider history in
Temporal Workflow results / Harness PG events.
"""
from __future__ import annotations

import os
import re
from importlib.metadata import version
from temporalio import activity

RUNTIMES=("maf-harness","openai-agents")


async def _maf_agent(prompt: str, model: str, endpoint: str, credential: str) -> str:
    from agent_framework import create_harness_agent
    from agent_framework.openai import OpenAIChatClient
    agent=create_harness_agent(
        client=OpenAIChatClient(model=model,base_url=endpoint,api_key=credential),
        name="c09-maf-harness-runtime",
        disable_file_memory=True,disable_web_search=True,
        disable_tool_auto_approval=True,disable_compaction=True,
        default_options={"store":False,"max_output_tokens":120},
    )
    chunks=[]
    async for message in agent.run(prompt,session=agent.create_session(),stream=True):
        text=getattr(message,"text",None)
        if text: chunks.append(text)
    return "".join(chunks)


async def _openai_agent(prompt: str, model: str, endpoint: str, credential: str) -> str:
    from agents import Agent, AsyncOpenAI, OpenAIChatCompletionsModel, Runner, set_tracing_disabled
    set_tracing_disabled(disabled=True)
    async with AsyncOpenAI(base_url=endpoint,api_key=credential) as client:
        agent=Agent(
            name="c09-openai-agents-runtime",
            instructions="Reply with only the exact reference marker found in the user's input. No formatting, no explanation.",
            model=OpenAIChatCompletionsModel(model=model,openai_client=client),
        )
        result=await Runner.run(agent,prompt,max_turns=2)
        if not isinstance(result.final_output,str):
            raise RuntimeError("OpenAI Agents SDK did not return plain text")
        return result.final_output


ADAPTERS={"maf-harness":_maf_agent,"openai-agents":_openai_agent}


@activity.defn(name="c09_real_agent_runtime")
async def run_real_agent(request: dict) -> dict:
    from runtime_swap_facts import RuntimeFacts
    adapter=request.get("stage",{}).get("adapter")
    if adapter not in ADAPTERS:
        raise ValueError("Unknown/forbidden Agent Runtime")
    # Recovered Worker must use the frozen Agent SDK version, not merely
    # an adapter label with a silently upgraded implementation.
    installed=(f"maf-core-{version('agent-framework-core')}/openai-{version('agent-framework-openai')}"
               if adapter=="maf-harness" else f"openai-agents-{version('openai-agents')}")
    if installed!=request["stage"]["frozen_runtime_version"]:
        raise ValueError("C09 recovered Agent SDK runtime version differs from frozen binding")
    endpoint=os.environ.get("POC_C_LITELLM_BASE_URL","")
    credential=os.environ.get("JUSDA_LITELLM_API_KEY","")
    model=os.environ.get("POC_C_LITELLM_MODEL","")
    if not endpoint or not credential or not model:
        raise RuntimeError("C09 real runtime requires private process-only model config")
    RuntimeFacts(os.environ["POC_C_PLATFORM_DSN"]).require_frozen(
        request,request["stage"])
    code=request["expected_marker"]
    # Purposefully harmless bounded prompt, no arbitrary user content/tools.
    prompt=("Read this identifier and return exactly the identifier, "
            "without any other words or punctuation: "+code)
    text=await ADAPTERS[adapter](prompt,model,endpoint,credential)
    if not text or len(text)>4096:
        raise ValueError("Empty or oversized actual model answer")
    # Pass only a tiny normalized observation to History. Raw provider response
    # stays in this transient Worker Activity process and is never persisted.
    found=re.findall(r"C09-[0-9A-F]{8}",text)
    candidate=found[0] if len(set(found))==1 and found else ""
    return {
        "run_id":request["run_id"],
        "attempt_id":request["stage"]["attempt_id"],
        "adapter":adapter,
        "observed_marker":candidate,
        "output_chars":len(text),
        "real_model_called":True,
    }


@activity.defn(name="c09_independent_verify")
async def verify_runtime_model(request: dict) -> dict:
    from runtime_swap_facts import RuntimeFacts
    result=request["model_result"]
    stage=request["stage"]
    if (result["run_id"]!=request["run_id"] or
            result["attempt_id"]!=stage["attempt_id"] or
            result["adapter"]!=stage["adapter"] or
            result["real_model_called"] is not True):
        raise ValueError("Model Activity/Attempt lineage mismatch")
    return RuntimeFacts(os.environ["POC_C_PLATFORM_DSN"]).verify(
        request["run_id"],stage,result["observed_marker"],result["output_chars"])


@activity.defn(name="c09_finalize_platform_run")
async def finalize_runtime_swap(request:dict) -> dict:
    from runtime_swap_facts import RuntimeFacts
    store=RuntimeFacts(os.environ["POC_C_PLATFORM_DSN"])
    return (store.fail(request["run_id"]) if request.get("failed") is True
            else store.complete(request["run_id"]))
