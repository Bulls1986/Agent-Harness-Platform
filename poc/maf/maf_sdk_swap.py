"""A40: MAF Workflow using both native MAF Agent and another Agent SDK.

OpenAI Agents SDK is bridged through the public MAF BaseAgent /
SupportsAgentRun + AgentExecutor extension point, not a fake MAF agent.
Narrow contract: non-streaming responses only; no checkpoint or HITL swap.
Nothing touches platform DB: A23/C09 already test persisted task facts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from importlib.metadata import version
from typing import Never
from uuid import uuid4
import re

from agent_framework import (
    AgentExecutor, AgentExecutorRequest, AgentExecutorResponse, AgentResponse, BaseAgent,
    Executor, Message, WorkflowBuilder, WorkflowContext, handler,
)

ADAPTER="openai-agents"
FROZEN_SDK_VERSION="0.22.2"
PROMPT_TEMPLATE=(
    "Read this identifier and return exactly the identifier, "
    "without any other words or punctuation: {marker}"
)


@dataclass(frozen=True)
class PlatformStep:
    step_id: str
    attempt_id: str
    execution_id: str
    adapter: str


@dataclass(frozen=True)
class SwapContract:
    run_id: str
    marker: str
    steps: tuple[PlatformStep, PlatformStep]

    @classmethod
    def build(cls) -> "SwapContract":
        def uid(label: str) -> str:
            return f"{label}-{uuid4().hex}"
        return cls(
            run_id=uid("run"),
            marker="C09-"+uuid4().hex[:8].upper(),
            steps=tuple(
                PlatformStep(uid("step"),uid("attempt"),uid("execution"),adapter)
                for adapter in ("maf-harness",ADAPTER)
            ),
        )

    @property
    def prompt(self) -> str:
        return PROMPT_TEMPLATE.format(marker=self.marker)


@dataclass(frozen=True)
class StageFact:
    step_id: str
    attempt_id: str
    execution_id: str
    adapter: str
    passed: bool
    output_chars: int


@dataclass(frozen=True)
class ComparisonOutcome:
    run_id: str
    state: str
    facts: tuple[StageFact, ...]


class AgentSdkBridge(BaseAgent):
    """One external OpenAI Agents SDK wrapped as native MAF SupportsAgentRun.

    This example deliberately supports only run(stream=False). Native MAF
    streaming/session/checkpoint parity is a separate POC gate.
    """
    def __init__(self, *, model: str, endpoint: str, api_key: str):
        super().__init__(id="c09-openai-sdk-agent",name="c09-openai-agents-sdk")
        self.model=model
        self.endpoint=endpoint
        self._api_key=api_key

    async def run(self, messages=None, *, stream=False, session=None,
                  function_invocation_kwargs=None, client_kwargs=None):
        if stream:
            raise NotImplementedError("A40 streaming adapter not validated")
        if version("openai-agents")!=FROZEN_SDK_VERSION:
            raise ValueError("Frozen SDK version mismatch")
        # Data Plane exclusively: no shell, File Memory, Web, tools or tracing.
        from agents import Agent, AsyncOpenAI, OpenAIChatCompletionsModel, Runner, set_tracing_disabled
        set_tracing_disabled(disabled=True)
        if isinstance(messages,str):
            prompt=messages
        elif isinstance(messages,Message):
            prompt=messages.text
        else:
            prompt="\n".join(m.text for m in (messages or []) if isinstance(m,Message))
        if not prompt:
            raise ValueError("Empty AgentExecutor input")
        async with AsyncOpenAI(base_url=self.endpoint,api_key=self._api_key) as client:
            agent=Agent(
                name="a40-openai-sdk-adapter",
                instructions="Reply with only the exact reference marker found in the input. No formatting.",
                model=OpenAIChatCompletionsModel(model=self.model,openai_client=client),
            )
            result=await Runner.run(agent,prompt,max_turns=2)
        if not isinstance(result.final_output,str) or not result.final_output:
            raise ValueError("External Agent SDK produced no text")
        return AgentResponse(messages=[Message(role="assistant",contents=[result.final_output])],
                             agent_id=self.id)


class VerifyFirstExecutor(Executor):
    """Deterministically verify SDK-A before SDK-B gets its own prompt."""
    def __init__(self,contract:SwapContract,facts:list[StageFact]):
        super().__init__(id="a40-verify-maf")
        self.contract=contract
        self.facts=facts

    @handler
    async def verify(self, response: AgentExecutorResponse,
                     ctx: WorkflowContext[AgentExecutorRequest]) -> None:
        first=self.contract.steps[0]
        text=response.agent_response.text or ""
        passed=extract_marker(text)==self.contract.marker
        self.facts.append(StageFact(first.step_id,first.attempt_id,first.execution_id,
                                    first.adapter,passed,len(text)))
        if not passed:
            raise ValueError("MAF native Agent result failed independent Verify")
        # Independent second SDK receives the *same* original prompt, not
        # contextual output of the first agent (prevent chaining confound).
        await ctx.send_message(AgentExecutorRequest(
            messages=[Message(role="user",contents=[self.contract.prompt])]
        ))


class VerifySecondExecutor(Executor):
    def __init__(self,contract:SwapContract,facts:list[StageFact]):
        super().__init__(id="a40-verify-external")
        self.contract=contract
        self.facts=facts

    @handler
    async def verify(self, response: AgentExecutorResponse,
                     ctx: WorkflowContext[Never, ComparisonOutcome]) -> None:
        second=self.contract.steps[1]
        text=response.agent_response.text or ""
        passed=extract_marker(text)==self.contract.marker
        self.facts.append(StageFact(second.step_id,second.attempt_id,
                                    second.execution_id,second.adapter,passed,len(text)))
        if not passed:
            raise ValueError("External SDK result failed independent Verify")
        await ctx.yield_output(
            ComparisonOutcome(self.contract.run_id,"COMPLETED",tuple(self.facts)))


def extract_marker(text:str) -> str:
    # A bounded, deterministic verifier, no trusting model-reported success.
    matches=re.findall(r"C09-[0-9A-F]{8}",text)
    return matches[0] if len(matches)==1 else ""


def build_workflow(native_maf_agent,external_agent,contract:SwapContract,
                   recorded:list[StageFact]):
    first=AgentExecutor(native_maf_agent,id="a40-native-maf-agent")
    verify_first=VerifyFirstExecutor(contract,recorded)
    second=AgentExecutor(external_agent,id="a40-openai-sdk-adapter")
    verify_second=VerifySecondExecutor(contract,recorded)
    return (WorkflowBuilder(
        name="a40-maf-real-agent-sdk-switch",start_executor=first,
        output_from=[verify_second]
    ).add_edge(first,verify_first)
     .add_edge(verify_first,second)
     .add_edge(second,verify_second)
     .build())


async def run_comparison(native_maf_agent,external_agent,contract:SwapContract):
    facts:list[StageFact]=[]
    workflow=build_workflow(native_maf_agent,external_agent,contract,facts)
    result=await workflow.run(contract.prompt)
    outputs=result.get_outputs()
    if len(outputs)!=1 or not isinstance(outputs[0],ComparisonOutcome):
        raise AssertionError("MAF Workflow did not finish through trusted verifier")
    outcome=outputs[0]
    if (outcome.run_id!=contract.run_id or outcome.state!="COMPLETED" or
        tuple(s.adapter for s in outcome.facts)!=("maf-harness","openai-agents") or
        tuple(s.attempt_id for s in outcome.facts)!=tuple(s.attempt_id for s in contract.steps) or
        any(not s.passed for s in outcome.facts)):
        raise AssertionError("MAF Workflow swapped SDK but corrupted Harness identity/Verify")
    return outcome
