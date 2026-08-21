import os
from pathlib import Path
from typing import Any, TypedDict

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.tools import BaseTool, tool
from langchain_openai import ChatOpenAI


class CityTravelNotes(TypedDict):
    attractions: list[str]
    foods: list[str]
    transport: str


SYSTEM_PROMPT = (
    "你是中国本地旅行规划助手。根据用户需求选择合适工具，结合城市信息、"
    "预算判断和交通建议，输出可执行的每日景点、美食和交通安排。"
)

DEMO_QUESTION = (
    "我想带父母去北京玩3天，总预算3000元，喜欢历史文化和"
    "轻松一点的行程。请帮我规划每天的景点、美食和交通建议。"
)

CITY_NOTES: dict[str, CityTravelNotes] = {
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

load_dotenv(Path(__file__).with_name(".env"), override=False)


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Set {name} before running this LangChain sample.")
    return value


MODEL_CONFIG: dict[str, Any] = {
    "model": _required_env("MODEL_AGENT_NAME"),
    "api_key": _required_env("MODEL_AGENT_API_KEY"),
    "temperature": float(os.environ.get("MODEL_AGENT_TEMPERATURE", "0.2")),
}

model_api_base = os.environ.get("MODEL_AGENT_API_BASE", "").strip().rstrip("/")
if model_api_base:
    for suffix in ("/responses", "/chat/completions"):
        if model_api_base.endswith(suffix):
            model_api_base = model_api_base[: -len(suffix)]
            break
    MODEL_CONFIG["base_url"] = model_api_base


def _find_city(text: str, default: str = "北京") -> str:
    for city in CITY_NOTES:
        if city in text:
            return city
    return default


@tool
def search_travel_notes(query: str) -> str:
    """根据用户旅行需求或城市名，检索内置城市旅行资料。"""
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
    """根据城市、旅行天数和总预算，估算预算是否适合当前计划。"""
    daily_budget = budget // max(days, 1)
    if daily_budget >= 1000:
        level = "比较宽松"
    elif daily_budget >= 650:
        level = "中等可控"
    else:
        level = "偏紧，需要压缩住宿和餐饮成本"
    return (
        f"{city}{days}天总预算{budget}元，人均每日约{daily_budget}元，"
        f"预算判断：{level}。"
    )


@tool
def recommend_transport(city: str, travelers: str) -> str:
    """根据城市和同行人类型，给出适合的市内交通建议。"""
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


agent = create_agent(
    model=ChatOpenAI(**MODEL_CONFIG),
    tools=TRAVEL_TOOLS,
    system_prompt=SYSTEM_PROMPT,
)


if __name__ == "__main__":
    result = agent.invoke({"messages": [{"role": "user", "content": DEMO_QUESTION}]})
    print(result["messages"][-1].content)
