"""Opt-in real Responses-compatible model boundary for the Harness POC.

Runtime SDKs own model calls; this module owns only validated result shape and
human-readable report transformation. It is NOT a second orchestration engine.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from urllib.parse import urlsplit
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RequirementsDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    feature: str = Field(min_length=2, max_length=180)
    summary: str = Field(min_length=6, max_length=3000)
    capabilities: list[str] = Field(min_length=1, max_length=20)
    business_rules: list[str] = Field(min_length=1, max_length=20)
    acceptance_criteria: list[str] = Field(min_length=1, max_length=20)

    @field_validator("capabilities", "business_rules", "acceptance_criteria")
    @classmethod
    def nonblank(cls, items: list[str]) -> list[str]:
        if any(not s.strip() for s in items):
            raise ValueError("Blank requirements item")
        return items


class ReviewOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    decision: Literal["PASS", "NEEDS_WORK"]
    summary: str = Field(min_length=2, max_length=3000)
    issues: list[str] = Field(max_length=20)
    risks: list[str] = Field(max_length=20)
    recommendations: list[str] = Field(max_length=20)


@dataclass(frozen=True)
class ModelConfiguration:
    mode: Literal["deterministic_local_model", "live"]
    model_id: str | None = None
    base_url: str | None = None
    api_key: str | None = None

    @classmethod
    def from_env(cls) -> "ModelConfiguration":
        mode = os.environ.get("HARNESS_MODEL_MODE", "local").strip().lower()
        if mode == "local":
            return cls("deterministic_local_model")
        if mode != "live":
            raise ValueError("Unsupported HARNESS_MODEL_MODE; use local or live")
        base = os.environ.get("HARNESS_MODEL_BASE_URL", "").strip().rstrip("/")
        name = os.environ.get("HARNESS_MODEL_NAME", "").strip()
        key = (os.environ.get("HARNESS_MODEL_API_KEY")
               or os.environ.get("JUSDA_LITELLM_API_KEY") or "").strip()
        parsed = urlsplit(base)
        if (not name or not key or parsed.scheme not in ("https", "http")
                or not parsed.netloc or parsed.username or parsed.password):
            raise ValueError("Live model requires an endpoint URL, model name and credential")
        return cls(mode="live", model_id=name, base_url=base, api_key=key)


DRAFT_INSTRUCTIONS = """你是产品需求分析 Agent（Pydantic AI）。分析用户提交的企业软件功能需求。
仅返回严格 JSON 对象，不要 Markdown、代码块、解释、空值或额外字段。
字段：feature（短标题字符串），summary（具体业务概述字符串），
capabilities（至少一个具体功能点字符串数组），business_rules（至少一个业务规则字符串数组），
acceptance_criteria（至少一个可验证验收条件字符串数组）。
只做需求分析，不宣称功能已开发或测试通过。用中文回答。"""

REVIEW_INSTRUCTIONS = """你是独立需求审核 Agent（OpenAI Agents SDK）。
输入是经过平台持久化且已验证的需求分析 JSON。
审查业务规则、边界条件、验收可执行性、权限和失败处理。
仅返回严格 JSON 对象，不要 Markdown、代码块或额外字段。
decision 只能为 PASS 或 NEEDS_WORK；还需 summary 非空字符串，
issues / risks / recommendations 三个字符串数组（可以为空）。
如果存在明确缺漏，decision 必须为 NEEDS_WORK。不要声称真实软件已运行。中文回答。"""


def parse_requirements(text: str) -> RequirementsDraft:
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Draft must be a JSON object")
    return RequirementsDraft.model_validate(data)


def parse_review(text: str) -> ReviewOutcome:
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Review must be a JSON object")
    return ReviewOutcome.model_validate(data)


def render_business_report(draft: RequirementsDraft, review: ReviewOutcome) -> str:
    def lines(label: str, items: list[str]) -> str:
        return label + "\n" + "\n".join(
            f"{i}. {item.strip()}" for i, item in enumerate(items, 1)
        ) if items else label + "\n（无）"

    return "\n\n".join((
        "【需求分析】" + draft.feature,
        "业务概述\n" + draft.summary,
        lines("功能清单", draft.capabilities),
        lines("业务规则", draft.business_rules),
        lines("验收标准", draft.acceptance_criteria),
        "【独立审核】" + review.decision + "\n" + review.summary,
        lines("发现的问题", review.issues),
        lines("主要风险", review.risks),
        lines("改进建议", review.recommendations),
    ))


def make_pydantic_agent(config: ModelConfiguration):
    if config.mode != "live" or not config.model_id or not config.base_url or not config.api_key:
        raise ValueError("Live Pydantic Agent requires validated configuration")
    from pydantic_ai import Agent
    from pydantic_ai.models.openai import OpenAIResponsesModel
    from pydantic_ai.providers.openai import OpenAIProvider
    model = OpenAIResponsesModel(config.model_id, provider=OpenAIProvider(
        base_url=config.base_url, api_key=config.api_key
    ))
    return Agent(model, instructions=DRAFT_INSTRUCTIONS)


def make_openai_agent(config: ModelConfiguration):
    if config.mode != "live" or not config.model_id or not config.base_url or not config.api_key:
        raise ValueError("Live OpenAI Agent requires validated configuration")
    from openai import AsyncOpenAI
    from agents import Agent, set_tracing_disabled
    from agents.models.openai_responses import OpenAIResponsesModel
    # This local LiteLLM gateway does not have an OpenAI tracing key. Never
    # forward a private LiteLLM credential to OpenAI's tracing endpoint.
    set_tracing_disabled(True)
    return Agent(name="requirement-review", instructions=REVIEW_INSTRUCTIONS,
                 model=OpenAIResponsesModel(
                     model=config.model_id,
                     openai_client=AsyncOpenAI(base_url=config.base_url,
                                               api_key=config.api_key),
                 ))