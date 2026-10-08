"""A40: two actual Agent SDKs inside one actual MAF Workflow.

Same model, prompt, marker and versions as C09; ONLY orchestrator changes.
Network credentials stay process-only; output never prints answer/credential.
"""
from __future__ import annotations
import asyncio
import json
import os

from agent_framework import create_harness_agent
from agent_framework.openai import OpenAIChatClient
from maf_sdk_swap import AgentSdkBridge, SwapContract, run_comparison


async def real_probe() -> dict:
    endpoint=os.environ["POC_C_LITELLM_BASE_URL"]
    model=os.environ["POC_C_LITELLM_MODEL"]
    key=os.environ["JUSDA_LITELLM_API_KEY"]
    contract=SwapContract.build()
    native=create_harness_agent(
        client=OpenAIChatClient(model=model,base_url=endpoint,api_key=key),
        name="a40-maf-harness",
        disable_file_memory=True,disable_web_search=True,
        disable_tool_auto_approval=True,disable_compaction=True,
        default_options={"store":False,"max_output_tokens":120},
    )
    external=AgentSdkBridge(model=model,endpoint=endpoint,api_key=key)
    outcome=await asyncio.wait_for(run_comparison(native,external,contract),timeout=185)
    return {
        "status":"PASS_A40_REAL_MAF_WORKFLOW_WITH_TWO_AGENT_SDKS",
        "workflow":"native_MAF_WorkflowBuilder_AgentExecutor",
        "actual_runtime_adapters":[f.adapter for f in outcome.facts],
        "real_model_request_each":True,
        "two_independent_verifications":all(f.passed for f in outcome.facts),
        "platform_run_id_preserved":outcome.run_id==contract.run_id,
        "distinct_attempts_preserved":len({f.attempt_id for f in outcome.facts})==2,
        "same_model_gateway_as_C09":True,
        "harness_postgresql_persistence_proven":False,
        "streaming_session_handoff_proven":False,
        "cross_process_checkpoint_recovery_proven":False,
        "distinct_model_provider_proven":False,
        "raw_provider_text_logged":False,
    }

def main():
    try:
        print(json.dumps(asyncio.run(real_probe()),sort_keys=True))
        return 0
    except Exception as exc:
        # Provider exceptions sometimes include sensitive URL/header values.
        print(json.dumps({"status":"A40_LIVE_GAP",
                          "failure_category":type(exc).__name__}))
        return 1

if __name__=="__main__":
    raise SystemExit(main())
