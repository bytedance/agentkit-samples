from __future__ import annotations

import os
from typing import Any

from strands import Agent, tool
from strands.models.openai import OpenAIModel
from veadk.tools.builtin_tools.web_search import web_search as builtin_web_search


SYSTEM_PROMPT = (
    "你是北京及中国本地旅行规划助手，需要结合联网搜索、预算判断和用户偏好，"
    "给出可执行的每日景点、美食和交通建议。回答旅行规划问题时，优先调用 "
    "search_travel_web 获取上下文，并调用 estimate_trip_budget 判断预算。"
)


def _required_model_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _normalize_openai_api_base(api_base: str) -> str:
    base_url = api_base.strip().rstrip("/")
    for suffix in ("/responses", "/chat/completions"):
        if base_url.endswith(suffix):
            return base_url[: -len(suffix)]
    return base_url


def build_model() -> OpenAIModel:
    provider = _required_model_env("MODEL_AGENT_PROVIDER").lower()
    if provider != "openai":
        raise RuntimeError(
            f"Unsupported MODEL_AGENT_PROVIDER for this sample: {provider}"
        )

    return OpenAIModel(
        model_id=_required_model_env("MODEL_AGENT_NAME"),
        stream=False,
        client_args={
            "api_key": _required_model_env("MODEL_AGENT_API_KEY"),
            "base_url": _normalize_openai_api_base(
                _required_model_env("MODEL_AGENT_API_BASE")
            ),
        },
        params={
            "temperature": 0.2,
        },
    )


def _format_web_search_results(results: Any) -> str:
    if isinstance(results, str):
        return results
    if isinstance(results, list):
        return "\n".join(
            str(result).strip() for result in results if str(result).strip()
        )
    return str(results)


@tool
def search_travel_web(query: str) -> str:
    """根据用户旅行需求进行联网搜索，返回可用于规划的摘要。"""
    try:
        result = _format_web_search_results(builtin_web_search(query))
    except Exception as exc:
        return f"联网搜索失败：{exc}。搜索词：{query}"
    return result or f"联网搜索没有返回可解析结果。搜索词：{query}"


@tool
def estimate_trip_budget(city: str, days: int, budget: int) -> str:
    """估算国内城市旅行预算是否宽松。"""
    daily = budget // max(days, 1)
    if daily >= 1000:
        level = "比较宽松"
    elif daily >= 650:
        level = "中等可控"
    else:
        level = "偏紧，需要压缩住宿和餐饮成本"
    return f"{city}{days}天总预算{budget}元，人均每日约{daily}元，预算判断：{level}。"


TRAVEL_TOOLS = [search_travel_web, estimate_trip_budget]


def build_agent(model: OpenAIModel | None = None) -> Agent:
    """创建可被 agentkit migrate 识别的 Strands Agent。"""
    return Agent(
        name="strands_travel_planner",
        model=model or build_model(),
        tools=TRAVEL_TOOLS,
        system_prompt=SYSTEM_PROMPT,
        callback_handler=None,
    )


def _extract_agent_text(response: Any) -> str:
    if isinstance(response, str):
        return response
    message = getattr(response, "message", None)
    if isinstance(message, dict):
        blocks = message.get("content", [])
        return "".join(str(block.get("text", "")) for block in blocks)
    return str(response)


def invoke_agent(prompt: str) -> str:
    """使用 Strands Agent 调试入口，并返回可读文本。"""
    return _extract_agent_text(build_agent()(prompt))


if __name__ == "__main__":
    demo = "我想带父母去北京玩3天，总预算3000元，喜欢历史文化和轻松一点的行程。请帮我规划每天的景点、美食和交通建议。"
    print(invoke_agent(demo))
