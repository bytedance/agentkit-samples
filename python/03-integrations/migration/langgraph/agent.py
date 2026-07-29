import os
import re
from typing import Any, TypedDict

from langchain.agents import create_agent
from langchain_core.language_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import BaseTool, tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph


SYSTEM_PROMPT = (
    "你是中国本地旅行规划助手。根据用户需求选择合适工具，结合城市信息、"
    "预算判断和交通建议，输出可执行的每日景点、美食和交通安排。"
)


CITY_NOTES = {
    "北京": {
        "attractions": ["故宫博物院", "天坛公园", "什刹海胡同", "国家博物馆"],
        "foods": ["北京烤鸭", "炸酱面", "铜锅涮肉"],
        "transport": "核心景点适合地铁串联，带长辈时减少跨城区折返。",
    },
    "成都": {
        "attractions": ["武侯祠", "宽窄巷子", "人民公园", "太古里"],
        "foods": ["火锅", "钟水饺", "担担面"],
        "transport": "市区景点适合地铁加短距离打车，餐饮安排避开排队高峰。",
    },
    "杭州": {
        "attractions": ["西湖", "灵隐寺", "河坊街", "京杭大运河"],
        "foods": ["龙井虾仁", "片儿川", "定胜糕"],
        "transport": "西湖周边适合步行和公交，热门区域建议错峰出行。",
    },
}


class TravelState(TypedDict, total=False):
    question: str
    answer: str


def _find_city(text: str, default: str = "北京") -> str:
    for city in CITY_NOTES:
        if city in text:
            return city
    return default


def _extract_days(text: str, default: int = 3) -> int:
    match = re.search(r"(\d+)\s*天", text)
    return int(match.group(1)) if match else default


def _extract_budget(text: str, default: int = 3000) -> int:
    match = re.search(r"(?:预算|总预算)?\s*(\d{3,5})\s*元", text)
    return int(match.group(1)) if match else default


def _extract_travelers(text: str, default: str = "普通出行") -> str:
    if "父母" in text or "长辈" in text:
        return "带父母/长辈"
    if "孩子" in text or "亲子" in text:
        return "亲子"
    if "朋友" in text or "同学" in text:
        return "朋友同行"
    return default


def _openai_base_url(api_base: str) -> str:
    base_url = api_base.strip().rstrip("/")
    for suffix in ("/responses", "/chat/completions"):
        if base_url.endswith(suffix):
            return base_url[: -len(suffix)]
    return base_url


@tool
def search_travel_notes(query: str) -> str:
    """检索用户项目内置的城市旅行资料，返回景点、美食和出行提示。"""
    city = _find_city(query)
    notes = CITY_NOTES[city]
    return (
        f"{city}旅行资料："
        f"推荐景点：{'、'.join(notes['attractions'])}；"
        f"推荐美食：{'、'.join(notes['foods'])}；"
        f"出行提示：{notes['transport']}"
    )


@tool
def estimate_trip_budget(city: str, days: int, budget: int) -> str:
    """估算指定城市、天数和总预算是否适合当前旅行计划。"""
    daily = budget // max(days, 1)
    if daily >= 1000:
        level = "比较宽松"
    elif daily >= 650:
        level = "中等可控"
    else:
        level = "偏紧，需要压缩住宿和餐饮成本"
    return f"{city}{days}天总预算{budget}元，人均每日约{daily}元，预算判断：{level}。"


@tool
def recommend_transport(city: str, travelers: str) -> str:
    """根据城市和同行人类型给出简单交通建议。"""
    base = CITY_NOTES.get(city, CITY_NOTES["北京"])["transport"]
    if "父母" in travelers or "长辈" in travelers:
        return f"{base} 建议每天只安排1到2个核心区域，并预留午休。"
    if "亲子" in travelers:
        return f"{base} 建议优先选择换乘少、步行距离短的路线。"
    return base


TRAVEL_TOOLS: list[BaseTool] = [
    search_travel_notes,
    estimate_trip_budget,
    recommend_transport,
]


class ToolCallingDemoChatModel(FakeMessagesListChatModel):
    """Demo chat model that lets LangGraph bind tools during local runs."""

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ToolCallingDemoChatModel":
        del tools, kwargs
        return self


def _build_chat_model() -> Any:
    model_name = os.environ.get("MODEL_AGENT_NAME", "").strip()
    api_key = os.environ.get("MODEL_AGENT_API_KEY", "").strip()
    if model_name and api_key:
        kwargs: dict[str, Any] = {
            "model": model_name,
            "api_key": api_key,
            "temperature": float(os.environ.get("MODEL_AGENT_TEMPERATURE", "0.2")),
        }
        api_base = os.environ.get("MODEL_AGENT_API_BASE", "").strip()
        if api_base:
            kwargs["base_url"] = _openai_base_url(api_base)
        return ChatOpenAI(**kwargs)

    return ToolCallingDemoChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_travel_notes",
                        "args": {"query": "北京 3天 父母 历史文化 轻松行程"},
                        "id": "call_search_travel_notes",
                    },
                    {
                        "name": "estimate_trip_budget",
                        "args": {"city": "北京", "days": 3, "budget": 3000},
                        "id": "call_estimate_trip_budget",
                    },
                    {
                        "name": "recommend_transport",
                        "args": {"city": "北京", "travelers": "带父母/长辈"},
                        "id": "call_recommend_transport",
                    },
                ],
            ),
            AIMessage(
                content=(
                    "北京3天旅行规划（示例模型输出）\n\n"
                    "第1天：故宫博物院 + 什刹海胡同，午餐安排炸酱面，晚上尝试铜锅涮肉。\n"
                    "第2天：天坛公园 + 前门周边，节奏放慢，下午预留休息时间。\n"
                    "第3天：国家博物馆 + 老北京美食体验，避开早晚高峰返程。\n\n"
                    "预算建议：3000元三天人均每日约1000元，整体比较宽松。\n"
                    "交通建议：优先地铁和短距离打车，每天控制在1到2个核心区域。"
                )
            ),
        ]
    )


react_agent = create_agent(
    model=_build_chat_model(),
    tools=TRAVEL_TOOLS,
    system_prompt=SYSTEM_PROMPT,
)


def _extract_question(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("question", "input", "prompt"):
            text = value.get(key)
            if isinstance(text, str) and text.strip():
                return text
        messages = value.get("messages")
        if isinstance(messages, list) and messages:
            return _extract_question(messages[-1])
    content = getattr(value, "content", None)
    if isinstance(content, str):
        return content
    return str(value)


def _message_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    content = getattr(value, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(value, dict):
        messages = value.get("messages")
        if isinstance(messages, list) and messages:
            return _message_text(messages[-1])
    return str(value)


def call_react_agent(state: TravelState) -> TravelState:
    question = _extract_question(state)
    result = react_agent.invoke({"messages": [HumanMessage(content=question)]})
    return {"answer": _message_text(result)}


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
