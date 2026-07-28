from __future__ import annotations

import asyncio
import os
import re
from collections.abc import AsyncIterator
from typing import Any

import litellm
from langchain_core.runnables import Runnable
from langchain_core.tools import tool
from veadk.tools.builtin_tools.web_search import web_search as builtin_web_search


SYSTEM_PROMPT = (
    "你是北京及中国本地旅行规划助手，需要结合联网搜索、预算判断和用户偏好，"
    "给出可执行的每日景点、美食和交通建议。"
)


def _litellm_model_name(model_name: str, provider: str) -> str:
    normalized = model_name.strip()
    if "/" in normalized:
        return normalized
    normalized_provider = provider.strip()
    return f"{normalized_provider}/{normalized}" if normalized_provider else normalized


def _litellm_base_url(api_base: str) -> str:
    base_url = api_base.strip().rstrip("/")
    for suffix in ("/responses", "/chat/completions"):
        if base_url.endswith(suffix):
            return base_url[: -len(suffix)]
    return base_url


def _required_model_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _value(data: Any, name: str) -> Any:
    if isinstance(data, dict):
        return data[name]
    return getattr(data, name)


def _litellm_content(response: Any) -> str:
    choice = _value(response, "choices")[0]
    message = _value(choice, "message")
    content = _value(message, "content")
    if isinstance(content, list):
        return "\n".join(str(part) for part in content)
    return str(content)


def _section(text: str, start: str, end: str) -> str:
    if start not in text:
        return ""
    section = text.split(start, 1)[1]
    if end in section:
        section = section.split(end, 1)[0]
    return section.strip()


def _fallback_model_response(messages: list[dict[str, str]], reason: str) -> str:
    prompt = messages[-1]["content"] if messages else ""
    search_context = _section(prompt, "联网搜索结果：", "预算建议：")
    budget_result = _section(prompt, "预算建议：", "请输出")
    return (
        "北京3天旅行规划\n\n"
        f"联网搜索：{search_context or '当前未取得可用搜索结果。'}\n"
        f"预算建议：{budget_result or '当前未取得可用预算判断。'}\n\n"
        "第1天：故宫博物院 + 什刹海胡同\n"
        "第2天：天坛公园 + 前门大街\n"
        "第3天：国家博物馆 + 南锣鼓巷\n\n"
        "交通建议：优先选择地铁和短距离打车，连续景点尽量按同一区域串联。\n"
        f"说明：LiteLLM 模型调用失败，已返回本地兜底结果。原因：{reason}"
    )


class LiteLLMTravelModel(Runnable[Any, str]):
    """LangChain Runnable model node backed by LiteLLM."""

    def __init__(
        self,
        model_name: str | None = None,
        provider: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.2,
    ) -> None:
        self.model_name = model_name or _required_model_env("MODEL_AGENT_NAME")
        self.provider = provider or _required_model_env("MODEL_AGENT_PROVIDER")
        self.model = _litellm_model_name(self.model_name, self.provider)
        self.base_url = _litellm_base_url(
            base_url or _required_model_env("MODEL_AGENT_API_BASE")
        )
        self.api_key = api_key or _required_model_env("MODEL_AGENT_API_KEY")
        self.temperature = temperature

    def invoke(self, input: Any, config: Any | None = None, **kwargs: Any) -> str:
        del config
        messages = (
            input
            if isinstance(input, list)
            else [{"role": "user", "content": str(input)}]
        )
        try:
            response = litellm.completion(
                model=self.model,
                base_url=self.base_url,
                api_key=self.api_key,
                temperature=self.temperature,
                timeout=60,
                messages=messages,
                **kwargs,
            )
            return _litellm_content(response)
        except Exception as exc:
            return _fallback_model_response(messages, str(exc))

    async def ainvoke(
        self, input: Any, config: Any | None = None, **kwargs: Any
    ) -> str:
        del config
        return self.invoke(input, **kwargs)


def build_model_agent() -> LiteLLMTravelModel:
    return LiteLLMTravelModel()


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
            last = messages[-1]
            if isinstance(last, dict):
                content = last.get("content")
                if isinstance(content, str):
                    return content
            content = getattr(last, "content", None)
            if isinstance(content, str):
                return content
    return str(value)


def _parse_city(question: str, default: str = "北京") -> str:
    direct_patterns = (
        r"(?:去|到)([\u4e00-\u9fff]{2,6})(?:玩|旅游|旅行)",
        r"([\u4e00-\u9fff]{2,6})(?:玩|旅游|旅行)",
    )
    for pattern in direct_patterns:
        match = re.search(pattern, question)
        if match:
            return match.group(1)

    city_hints = (
        "北京",
        "上海",
        "杭州",
        "成都",
        "西安",
        "南京",
        "重庆",
        "广州",
        "深圳",
    )
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


def _extract_terms(
    context: str, suffixes: tuple[str, ...], fallback: list[str]
) -> list[str]:
    suffix_pattern = "|".join(re.escape(suffix) for suffix in suffixes)
    terms = re.findall(
        rf"[\u4e00-\u9fffA-Za-z0-9]{{2,18}}(?:{suffix_pattern})", context
    )
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


def _day_plan(
    day: int, attractions: list[str], foods: list[str], travelers: str
) -> str:
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


def _collect_travel_context(question: str) -> dict[str, Any]:
    city = _parse_city(question)
    days = _parse_days(question)
    budget = _parse_budget(question)
    travelers = _parse_travelers(question)
    interests = _parse_interests(question)
    search_query = _build_search_query(city, days, budget, travelers, interests)
    search_context = search_travel_web.invoke({"query": search_query})
    budget_result = estimate_trip_budget.invoke(
        {"city": city, "days": days, "budget": budget}
    )
    return {
        "question": question,
        "city": city,
        "days": days,
        "budget": budget,
        "travelers": travelers,
        "interests": interests,
        "search_context": search_context,
        "budget_result": budget_result,
    }


def _render_model_messages(context: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"用户问题：{context['question']}\n"
                f"旅行参数：城市={context['city']}；天数={context['days']}；"
                f"预算={context['budget']}元；同行={context['travelers']}；"
                f"偏好={'、'.join(context['interests'])}\n\n"
                f"联网搜索结果：\n{context['search_context']}\n\n"
                f"预算建议：\n{context['budget_result']}\n\n"
                "请输出包含标题、每日行程、交通建议和说明的中文旅行规划。"
            ),
        },
    ]


def build_itinerary(question: str) -> str:
    context = _collect_travel_context(question)
    return build_model_agent().invoke(_render_model_messages(context))


class TravelPlanningRunnable(Runnable[Any, str]):
    """一个可迁移的 LangChain Runnable 旅游规划 agent。"""

    def invoke(self, input: Any, config: Any | None = None, **kwargs: Any) -> str:
        del config, kwargs
        return build_itinerary(_extract_question(input))

    async def ainvoke(
        self, input: Any, config: Any | None = None, **kwargs: Any
    ) -> str:
        del config, kwargs
        return self.invoke(input)

    async def astream(
        self,
        input: Any,
        config: Any | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        del config, kwargs
        answer = self.invoke(input)
        for block in answer.split("\n\n"):
            await asyncio.sleep(0)
            yield f"{block}\n\n"


agent = TravelPlanningRunnable()


if __name__ == "__main__":
    demo = {
        "question": "我想带父母去北京玩3天，总预算3000元，喜欢历史文化和轻松一点的行程。请帮我规划每天的景点、美食和交通建议。"
    }
    print(agent.invoke(demo))
