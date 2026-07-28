from __future__ import annotations

import re
from typing import Any, TypedDict

from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from veadk.tools.builtin_tools.web_search import web_search as builtin_web_search


class TravelState(TypedDict, total=False):
    question: str
    city: str
    days: int
    budget: int
    interests: list[str]
    travelers: str
    search_query: str
    search_context: str
    budget_note: str
    answer: str
    request_count: int


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
    if "同学" in question or "朋友" in question:
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


def parse_request(state: TravelState) -> TravelState:
    question = state.get("question", "")
    city = _parse_city(question, state.get("city", "北京"))
    days = _parse_days(question, int(state.get("days", 3)))
    budget = _parse_budget(question, int(state.get("budget", 3000)))
    travelers = _parse_travelers(question, state.get("travelers", "普通出行"))
    return {
        "question": question,
        "city": city,
        "days": days,
        "budget": budget,
        "travelers": travelers,
        "interests": _parse_interests(question),
        "request_count": int(state.get("request_count", 0)) + 1,
    }


def _build_search_query(state: TravelState) -> str:
    city = state.get("city", "北京")
    days = int(state.get("days", 3))
    budget = int(state.get("budget", 3000))
    travelers = state.get("travelers", "普通出行")
    interests = state.get("interests", ["经典景点", "当地美食"])
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


def search_travel_context(state: TravelState) -> TravelState:
    city = state.get("city", "北京")
    days = int(state.get("days", 3))
    budget = int(state.get("budget", 3000))
    query = _build_search_query(state)
    return {
        "search_query": query,
        "search_context": search_travel_web.invoke({"query": query}),
        "budget_note": estimate_trip_budget.invoke(
            {"city": city, "days": days, "budget": budget}
        ),
    }


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


def build_final_answer(state: TravelState) -> TravelState:
    city = state.get("city", "北京")
    days = int(state.get("days", 3))
    budget = int(state.get("budget", 3000))
    travelers = state.get("travelers", "普通出行")
    search_context = state.get("search_context", "")
    attractions = _attractions_from_context(search_context)
    foods = _foods_from_context(search_context)
    plans = "\n\n".join(
        _day_plan(day, attractions, foods, travelers) for day in range(1, days + 1)
    )
    lines = [
        f"{city}{days}天旅行规划（预算{budget}元，{travelers}，第{state.get('request_count', 1)}次规划）",
        "",
        f"需求偏好：{', '.join(state.get('interests', ['经典景点']))}。",
        f"联网搜索：{search_context}",
        f"预算建议：{state.get('budget_note', '')}",
        "",
        plans,
        "",
        "交通建议：优先选择地铁和短距离打车，连续景点尽量按同一区域串联。",
        "说明：这是 LangGraph 迁移示例，旅行上下文来自搜索 tool；搜索能力由 veadk.tools.builtin_tools.web_search 提供。",
    ]
    return {"answer": "\n".join(lines)}


builder = StateGraph(TravelState)
builder.add_node("parse_request", parse_request)
builder.add_node("search_travel_context", search_travel_context)
builder.add_node("build_final_answer", build_final_answer)
builder.add_edge(START, "parse_request")
builder.add_edge("parse_request", "search_travel_context")
builder.add_edge("search_travel_context", "build_final_answer")
builder.add_edge("build_final_answer", END)

agent = builder.compile(checkpointer=InMemorySaver())


if __name__ == "__main__":
    result = agent.invoke(
        {
            "question": "我想带父母去北京玩3天，总预算3000元，喜欢历史文化、胡同和老北京美食，行程轻松一点。请帮我规划每天的景点、美食和交通建议。"
        },
        config={"configurable": {"thread_id": "local-demo"}},
    )
    print(result["answer"])
