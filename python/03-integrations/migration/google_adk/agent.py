import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.models import OpenAILlm
from google.adk.runners import InMemoryRunner
from google.genai import types


_ENV_FILE = Path(__file__).with_name(".env")
load_dotenv(_ENV_FILE, override=False)

SYSTEM_PROMPT = (
    "你是中国本地旅行规划助手。根据用户需求选择合适工具，结合城市信息、"
    "预算判断和交通建议，输出可执行的每日景点、美食和交通安排。"
)
os.environ.setdefault("ADK_DISABLE_JSON_SCHEMA_FOR_FUNC_DECL", "1")
DEMO_QUESTION = "我想去北京玩3天"


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


def _env(name: str) -> str:
    return os.environ[name].strip()


def _find_city(text: str, default: str = "北京") -> str:
    for city in CITY_NOTES:
        if city in text:
            return city
    return default


def _openai_base_url(api_base: str) -> str:
    base_url = api_base.strip().rstrip("/")
    for suffix in ("/responses", "/chat/completions"):
        if base_url.endswith(suffix):
            return base_url[: -len(suffix)]
    return base_url


def create_model() -> OpenAILlm:
    os.environ["OPENAI_API_KEY"] = _env("MODEL_AGENT_API_KEY")
    os.environ["OPENAI_BASE_URL"] = _openai_base_url(_env("MODEL_AGENT_API_BASE"))
    return OpenAILlm(model=_env("MODEL_AGENT_NAME"))


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


def recommend_transport(city: str, travelers: str) -> str:
    """根据城市和同行人类型给出简单交通建议。"""
    base = CITY_NOTES.get(city, CITY_NOTES["北京"])["transport"]
    if "父母" in travelers or "长辈" in travelers:
        return f"{base} 建议每天只安排1到2个核心区域，并预留午休。"
    if "亲子" in travelers:
        return f"{base} 建议优先选择换乘少、步行距离短的路线。"
    return base


def build_daily_itinerary(city: str, days: int, pace: str) -> str:
    """按城市、天数和节奏偏好生成简短的每日游玩安排。"""
    notes = CITY_NOTES.get(city, CITY_NOTES["北京"])
    daily_count = 1 if "轻松" in pace or "慢" in pace else 2
    lines = []
    for day in range(1, max(days, 1) + 1):
        start = (day - 1) * daily_count
        attractions = [
            notes["attractions"][(start + index) % len(notes["attractions"])]
            for index in range(daily_count)
        ]
        food = notes["foods"][(day - 1) % len(notes["foods"])]
        lines.append(f"第{day}天：{' + '.join(attractions)}，餐饮建议安排{food}。")
    return "\n".join(lines)


def suggest_food_stops(city: str, meal_count: int) -> str:
    """根据城市和餐次数量推荐本地特色餐饮安排。"""
    foods = CITY_NOTES.get(city, CITY_NOTES["北京"])["foods"]
    stops = [foods[index % len(foods)] for index in range(max(meal_count, 1))]
    return f"{city}{meal_count}餐建议：{'、'.join(stops)}。"


def check_itinerary_pace(city: str, days: int, travelers: str) -> str:
    """检查行程节奏是否适合同行人类型，并给出压缩或放松建议。"""
    notes = CITY_NOTES.get(city, CITY_NOTES["北京"])
    attractions_per_day = len(notes["attractions"]) / max(days, 1)
    if "父母" in travelers or "长辈" in travelers or "亲子" in travelers:
        limit = 1.5
    else:
        limit = 2.0
    if attractions_per_day > limit:
        return f"{city}{days}天节奏偏满，建议删减到每天1到2个重点，并保留休息时间。"
    return f"{city}{days}天节奏可控，可以按兴趣加入餐饮或街区体验。"


TRAVEL_TOOLS = [
    search_travel_notes,
    estimate_trip_budget,
    recommend_transport,
    build_daily_itinerary,
    suggest_food_stops,
    check_itinerary_pace,
]


root_agent = Agent(
    name="google_adk_travel_planner",
    model=create_model(),
    description="Google ADK travel planning agent for AgentKit migration demo.",
    instruction=SYSTEM_PROMPT,
    tools=TRAVEL_TOOLS,
)

# Alias for migration tools or users that prefer agent.py:agent.
agent = root_agent


async def invoke(question: str) -> str:
    user_id = "demo_user"
    runner = InMemoryRunner(
        agent=root_agent,
        app_name="google_adk_travel_planner_demo",
    )
    session = await runner.session_service.create_session(
        app_name=runner.app_name,
        user_id=user_id,
    )
    message = types.Content(role="user", parts=[types.Part(text=question)])
    final_text = []

    async with runner:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=message,
        ):
            if event.is_final_response() and event.content and event.content.parts:
                final_text.extend(part.text or "" for part in event.content.parts)

    return "".join(final_text)


if __name__ == "__main__":
    print(asyncio.run(invoke(DEMO_QUESTION)))
