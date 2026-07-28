from __future__ import annotations

import re
from typing import Any

from strands import Agent, tool
from strands.models import Model
from veadk.tools.builtin_tools.web_search import web_search as builtin_web_search


SYSTEM_PROMPT = (
    "你是北京及中国本地旅行规划助手，需要结合联网搜索、预算判断和用户偏好，"
    "给出可执行的每日景点、美食和交通建议。"
)


def _format_web_search_results(results: Any) -> str:
    if isinstance(results, str):
        return results
    if isinstance(results, list):
        return "\n".join(str(result).strip() for result in results if str(result).strip())
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


def _parse_city(question: str, default: str = "北京") -> str:
    direct_patterns = (
        r"(?:去|到)([\u4e00-\u9fff]{2,6})(?:玩|旅游|旅行)",
        r"([\u4e00-\u9fff]{2,6})(?:玩|旅游|旅行)",
    )
    for pattern in direct_patterns:
        match = re.search(pattern, question)
        if match:
            return match.group(1)

    city_hints = ("北京", "上海", "杭州", "成都", "西安", "南京", "重庆", "广州", "深圳")
    for city in city_hints:
        if city in question:
            return city
    return default


def _parse_days(question: str, default: int = 3) -> int:
    match = re.search(r"(\d+)\s*天", question)
    return int(match.group(1)) if match else default


def _parse_budget(question: str, default: int = 3000) -> int:
    match = re.search(r"(?:预算|总预算)?\s*(\d{3,5})\s*元", question)
    return int(match.group(1)) if match else default


def _parse_travelers(question: str, default: str = "普通出行") -> str:
    if "父母" in question or "长辈" in question:
        return "带父母/长辈"
    if "孩子" in question or "亲子" in question:
        return "亲子"
    if "朋友" in question or "同学" in question:
        return "朋友同行"
    if "一个人" in question or "独自" in question:
        return "独自旅行"
    return default


def _parse_interests(question: str) -> list[str]:
    interests = []
    candidates = {
        "历史文化": ("历史", "文化", "故宫", "博物馆", "遗迹"),
        "胡同街区": ("胡同", "Citywalk", "街区"),
        "亲子活动": ("孩子", "亲子", "博物馆"),
        "城市景观": ("夜景", "城市", "轻轨", "外滩"),
        "当地美食": ("美食", "火锅", "小吃", "老北京", "餐饮"),
        "轻松慢游": ("轻松", "不想走太多路", "不太累", "休闲"),
    }
    for label, words in candidates.items():
        if any(word in question for word in words):
            interests.append(label)
    return interests or ["经典景点", "当地美食"]


def _build_search_query(
    city: str,
    days: int,
    budget: int,
    travelers: str,
    interests: list[str],
) -> str:
    parts = [
        city,
        f"{days}天",
        f"{budget}元",
        travelers,
        *interests,
        "旅游",
        "景点",
        "美食",
        "交通",
        "预约",
        "注意事项",
    ]
    return " ".join(part for part in parts if part and part != "普通出行")


def _unique(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        normalized = value.strip(" ，,；;。：:")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _extract_terms(context: str, suffixes: tuple[str, ...], fallback: list[str]) -> list[str]:
    suffix_pattern = "|".join(re.escape(suffix) for suffix in suffixes)
    terms = re.findall(rf"[\u4e00-\u9fffA-Za-z0-9]{{2,18}}(?:{suffix_pattern})", context)
    return _unique(terms)[:5] or fallback


def _attractions_from_context(context: str) -> list[str]:
    return _extract_terms(
        context,
        ("博物院", "博物馆", "公园", "胡同", "天坛", "景区", "街区", "场馆"),
        ["联网搜索结果中的核心景点", "同一区域可串联景点"],
    )


def _foods_from_context(context: str) -> list[str]:
    return _extract_terms(
        context,
        ("烤鸭", "炸酱面", "涮肉", "火锅", "小吃", "美食", "餐饮"),
        ["当地代表性美食", "交通便利区域餐厅"],
    )


def _day_plan(day: int, attractions: list[str], foods: list[str], travelers: str) -> str:
    morning = attractions[(day - 1) % len(attractions)]
    afternoon = attractions[day % len(attractions)]
    lunch = foods[(day - 1) % len(foods)]
    dinner = foods[day % len(foods)]
    pace_note = (
        "下午预留休息时间，减少连续步行。"
        if "父母" in travelers or "长辈" in travelers
        else "下午安排同一区域活动，避免来回折返。"
    )
    return "\n".join(
        [
            f"第{day}天：{morning} + {afternoon}",
            f"- 上午：优先安排{morning}，出发前确认预约和开放时间。",
            f"- 午餐：结合联网搜索结果尝试{lunch}，选择离上午景点较近的位置。",
            f"- 下午：前往{afternoon}，{pace_note}",
            f"- 晚餐：安排{dinner}，餐后就近返回住宿区域。",
        ]
    )


def build_itinerary(question: str) -> str:
    city = _parse_city(question)
    days = _parse_days(question)
    budget = _parse_budget(question)
    travelers = _parse_travelers(question)
    interests = _parse_interests(question)
    search_query = _build_search_query(city, days, budget, travelers, interests)
    search_context = search_travel_web(query=search_query)
    budget_result = estimate_trip_budget(city=city, days=days, budget=budget)
    attractions = _attractions_from_context(search_context)
    foods = _foods_from_context(search_context)
    plans = "\n\n".join(
        _day_plan(day, attractions, foods, travelers) for day in range(1, days + 1)
    )
    return (
        f"{city}{days}天旅行规划（预算{budget}元，{travelers}）\n\n"
        f"需求摘要：偏好{', '.join(interests)}。\n"
        f"联网搜索：{search_context}\n"
        f"预算建议：{budget_result}\n\n"
        f"{plans}\n\n"
        "交通建议：优先选择地铁和短距离打车，连续景点尽量按同一区域串联。\n"
        "说明：这是 Strands 迁移示例，旅行上下文来自 Strands tool；搜索能力由 veadk.tools.builtin_tools.web_search 提供。"
    )


class LocalTravelModel(Model):
    """用于本地调试和样例测试的 Strands Model。"""

    def update_config(self, **model_config: Any) -> None:
        self.model_config = model_config

    def get_config(self) -> dict[str, Any]:
        return getattr(self, "model_config", {})

    async def structured_output(
        self,
        output_model,
        prompt,
        system_prompt=None,
        **kwargs: Any,
    ):
        del prompt, system_prompt, kwargs
        yield {"output": output_model()}

    async def stream(
        self,
        messages,
        tool_specs=None,
        system_prompt=None,
        **kwargs: Any,
    ):
        del tool_specs, system_prompt, kwargs
        user_text = messages[-1]["content"][0]["text"]
        if "旅游" in user_text or "旅行" in user_text or "玩" in user_text:
            text = build_itinerary(user_text)
        else:
            text = f"Strands 北京旅游规划助手：我可以根据预算、天数和偏好规划北京旅游行程。收到：{user_text}"

        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockStart": {"start": {}}}
        yield {"contentBlockDelta": {"delta": {"text": text}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "end_turn"}}
        yield {
            "metadata": {
                "usage": {
                    "inputTokens": 1,
                    "outputTokens": max(1, len(text) // 4),
                    "totalTokens": max(2, len(text) // 4 + 1),
                },
                "metrics": {"latencyMs": 0},
            }
        }


def build_agent() -> Agent:
    """创建可被 agentkit migrate 识别的 Strands Agent。"""
    return Agent(
        name="strands_travel_planner",
        model=LocalTravelModel(),
        tools=TRAVEL_TOOLS,
        system_prompt=SYSTEM_PROMPT,
        callback_handler=None,
    )


agent = build_agent()


def invoke_agent(prompt: str) -> str:
    """使用 Strands Agent 调试入口，并返回可读文本。"""
    return str(agent(prompt))


if __name__ == "__main__":
    demo = "我想带父母去北京玩3天，总预算3000元，喜欢历史文化和轻松一点的行程。请帮我规划每天的景点、美食和交通建议。"
    print(invoke_agent(demo))
