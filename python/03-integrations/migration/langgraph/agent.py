from __future__ import annotations

import os
from typing import Any, TypedDict

from langchain.chat_models import init_chat_model
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import create_react_agent
from veadk.tools.builtin_tools.web_search import web_search as builtin_web_search


SYSTEM_PROMPT = (
    "你是北京及中国本地旅行规划助手。请根据用户问题自主决定是否调用工具，"
    "结合联网搜索、预算判断和用户偏好，输出中文旅行方案。方案需要包含标题、"
    "每日景点安排、美食建议、交通建议、预算判断和必要注意事项。"
)


class TravelState(TypedDict, total=False):
    question: str
    answer: str


def _required_model_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _normalize_model_api_base(api_base: str) -> str:
    base_url = api_base.rstrip("/")
    for suffix in ("/responses", "/chat/completions"):
        if base_url.endswith(suffix):
            return base_url[: -len(suffix)]
    return base_url


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


def _create_chat_model():
    return init_chat_model(
        model=_required_model_env("MODEL_AGENT_NAME"),
        model_provider=_required_model_env("MODEL_AGENT_PROVIDER"),
        api_key=_required_model_env("MODEL_AGENT_API_KEY"),
        base_url=_normalize_model_api_base(_required_model_env("MODEL_AGENT_API_BASE")),
        temperature=0.2,
    )


react_agent = create_react_agent(
    model=_create_chat_model(),
    tools=[search_travel_web, estimate_trip_budget],
    prompt=SYSTEM_PROMPT,
)


def call_react_agent(state: TravelState) -> TravelState:
    result = react_agent.invoke({"messages": [("user", state["question"])]})
    answer = result["messages"][-1].content
    return {"answer": answer if isinstance(answer, str) else str(answer)}


def build_graph():
    builder = StateGraph(TravelState)
    builder.add_node("call_react_agent", call_react_agent)

    builder.add_edge(START, "call_react_agent")
    builder.add_edge("call_react_agent", END)
    return builder.compile(checkpointer=InMemorySaver())


agent = build_graph()


if __name__ == "__main__":
    result = agent.invoke(
        {
            "question": (
                "我想带父母去北京玩3天，总预算3000元，喜欢历史文化、胡同和"
                "老北京美食，行程轻松一点。请帮我规划每天的景点、美食和交通建议。"
            )
        },
        config={"configurable": {"thread_id": "local-demo"}},
    )
    print(result["answer"])
