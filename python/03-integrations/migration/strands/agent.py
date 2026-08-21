import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from strands import Agent, tool
from strands.models.openai import OpenAIModel


SYSTEM_PROMPT = (
    "你是中国本地旅行规划助手。根据用户需求选择合适工具，结合城市信息、"
    "预算判断和交通建议，输出可执行的每日景点、美食和交通安排。"
)

_ENV_FILE = Path(__file__).with_name(".env")
load_dotenv(_ENV_FILE)


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, "").strip() or default


def _required_env(name: str) -> str:
    value = _env(name)
    if not value:
        raise RuntimeError(f"Set {name} before running this Strands sample.")
    return value


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
    "西安": {
        "attractions": ["陕西历史博物馆", "大雁塔", "城墙", "回民街"],
        "foods": ["肉夹馍", "羊肉泡馍", "凉皮"],
        "transport": "历史景点集中度高，适合地铁加步行，夜间美食街建议打车返回。",
    },
}


def _find_city(text: str, default: str = "北京") -> str:
    for city in CITY_NOTES:
        if city in text:
            return city
    return default


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


TRAVEL_TOOLS = [
    search_travel_notes,
    estimate_trip_budget,
    recommend_transport,
]


def _openai_base_url(api_base: str) -> str:
    base_url = api_base.strip().rstrip("/")
    for suffix in ("/responses", "/chat/completions"):
        if base_url.endswith(suffix):
            return base_url[: -len(suffix)]
    return base_url


def create_model() -> OpenAIModel:
    client_args: dict[str, str] = {"api_key": _required_env("MODEL_AGENT_API_KEY")}

    api_base = _env("MODEL_AGENT_API_BASE")
    if api_base:
        client_args["base_url"] = _openai_base_url(api_base)

    return OpenAIModel(
        model_id=_required_env("MODEL_AGENT_NAME"),
        stream=False,
        client_args=client_args,
        params={
            "temperature": float(_env("MODEL_AGENT_TEMPERATURE", "0.2")),
            "extra_body": {"thinking": {"type": "disabled"}},
        },
    )


def agent() -> Agent:
    """Create the native Strands Agent used by AgentKit migration."""
    return Agent(
        name="strands_travel_planner",
        model=create_model(),
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
    """Run the native Strands Agent and return readable text for local debugging."""
    return _extract_agent_text(agent()(prompt))


if __name__ == "__main__":
    demo = (
        "我想带父母去北京玩3天，总预算3000元，喜欢历史文化和轻松一点的行程。"
        "请帮我规划每天的景点、美食和交通建议。"
    )
    print(invoke_agent(demo))
