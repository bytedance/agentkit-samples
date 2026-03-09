"""
钩子分析输出修复 Hook。

核心策略（对齐 multimedia 的契约化思想）：
1. 仅对目标 agent（hook_format_agent / hook_analyzer_agent）生效；
2. 优先识别工具调用轮次，避免污染 transfer_to_agent 等内部 envelope；
3. 无论 JSON 是否完美，都尽力写回结构化 state 并输出 Markdown；
4. best-effort：永远不给用户上屏原始 JSON/占位片段。
"""

import json
import re
from typing import Any, Optional

import json_repair
from google.adk.agents.callback_context import CallbackContext
from google.adk.events import Event
from google.adk.models import LlmResponse
from veadk.utils.logger import get_logger

logger = get_logger(__name__)

_TARGET_AGENTS = {"hook_agent"}
_MAX_COMMENT_LEN = 800

_SCORE_FIELDS = (
    "overall_score",
    "visual_impact",
    "language_hook",
    "emotion_trigger",
    "information_density",
    "rhythm_control",
)

# 中文字段名到英文字段名的映射，用于从 LLM Markdown 输出中提取各维度分数
_ZH_SCORE_MAPPINGS = {
    "visual_impact": r"视觉冲击力",
    "language_hook": r"语言钩子",
    "emotion_trigger": r"情绪唤起",
    "information_density": r"信息密度",
    "rhythm_control": r"节奏掌控",
}

# 中文维度标题到 comment 字段名的映射，用于精确提取各维度评价文本
_ZH_COMMENT_MAPPINGS = {
    "visual_comment": r"视觉冲击力",
    "language_comment": r"语言钩子",
    "emotion_comment": r"情绪唤起",
    "info_comment": r"信息密度",
    "rhythm_comment": r"节奏掌控",
}

_DEFAULT_HOOK_ANALYSIS: dict[str, Any] = {
    "overall_score": 0.0,
    "visual_impact": 0.0,
    "visual_comment": "",
    "language_hook": 0.0,
    "language_comment": "",
    "emotion_trigger": 0.0,
    "emotion_comment": "",
    "information_density": 0.0,
    "info_comment": "",
    "rhythm_control": 0.0,
    "rhythm_comment": "",
    "hook_type": "未知",
    "hook_type_analysis": "",
    "target_audience": "",
    "strengths": [],
    "weaknesses": [],
    "suggestions": [],
    "competitor_reference": "",
    "retention_prediction": "数据不足，基于当前信息暂无法稳定预测",
}


def _agent_name(callback_context: CallbackContext) -> str:
    inv = getattr(callback_context, "_invocation_context", None)
    if not inv:
        return ""
    return getattr(getattr(inv, "agent", None), "name", "") or ""


def _get_first_text(llm_response: Optional[LlmResponse]) -> str:
    if not llm_response or not llm_response.content or not llm_response.content.parts:
        return ""
    return str(llm_response.content.parts[0].text or "")


def _event_to_text(event: Optional[Event]) -> str:
    if event is None:
        return ""
    try:
        if hasattr(event, "model_dump"):
            return json.dumps(event.model_dump(), ensure_ascii=False)
    except Exception:
        pass
    try:
        return json.dumps(
            getattr(event, "__dict__", {}), ensure_ascii=False, default=str
        )
    except Exception:
        return str(event)


def _looks_like_tool_envelope(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    if "name" in payload and "parameters" in payload:
        return True
    if payload.get("agent_name") or payload.get("transfer_to_agent"):
        return True
    return False


def _has_hook_fields(parsed: dict) -> bool:
    """判断解析结果是否含有有意义的钩子分析字段。
    防止 json_repair 将 Markdown 文本错误解析为空 {}，进而导致全 0.0 默认值。
    """
    hook_fields = {
        "overall_score",
        "visual_impact",
        "language_hook",
        "emotion_trigger",
        "information_density",
        "rhythm_control",
        "visual_comment",
        "language_comment",
        "emotion_comment",
        "hook_type",
    }
    return bool(hook_fields & set(parsed.keys()))


def _is_tool_call_turn(model_response_event: Optional[Event], text: str) -> bool:
    event_text = _event_to_text(model_response_event).lower()
    if any(
        token in event_text
        for token in (
            "tool_call",
            "function_call",
            "function_response",
            "transfer_to_agent",
            "analyze_hook_segments",
        )
    ):
        return True

    stripped = text.strip()
    if not stripped:
        return False
    try:
        obj = json.loads(stripped)
        return _looks_like_tool_envelope(obj)
    except Exception:
        return False


def _extract_json_candidate(text: str) -> str:
    """提取 JSON 候选文本，优先从代码块中提取，否则尝试提取第一个 JSON 对象"""
    # 优先从代码块中提取
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, flags=re.IGNORECASE)
    if fenced and fenced.group(1).strip():
        return fenced.group(1).strip()

    # 如果没有代码块，尝试提取第一个完整的 JSON 对象（从 { 到匹配的 }）
    stripped = text.strip()
    if stripped.startswith("{"):
        # 尝试找到匹配的闭合括号
        brace_count = 0
        end_pos = -1
        for i, char in enumerate(stripped):
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0:
                    end_pos = i + 1
                    break
        if end_pos > 0:
            return stripped[:end_pos]

    return stripped


def _coerce_to_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    return [str(value)]


def _clamp_score(value: Any) -> float:
    try:
        return max(0.0, min(10.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _safe_text(value: Any, max_len: int = _MAX_COMMENT_LEN) -> str:
    text = str(value or "").strip()
    text = re.sub(r"<\[PLHD[^\]]*\]>", "", text)
    text = text.replace("transfer_to_agent", "")
    if len(text) > max_len:
        return text[: max_len - 1] + "..."
    return text


def _normalize_output(raw: dict[str, Any]) -> dict[str, Any]:
    output = {**_DEFAULT_HOOK_ANALYSIS, **(raw or {})}

    for field in _SCORE_FIELDS:
        output[field] = _clamp_score(output.get(field, 0))

    output["strengths"] = _coerce_to_list(output.get("strengths"))
    output["weaknesses"] = _coerce_to_list(output.get("weaknesses"))
    output["suggestions"] = _coerce_to_list(output.get("suggestions"))

    for field in (
        "visual_comment",
        "language_comment",
        "emotion_comment",
        "info_comment",
        "rhythm_comment",
        "hook_type",
        "hook_type_analysis",
        "target_audience",
        "competitor_reference",
        "retention_prediction",
    ):
        output[field] = _safe_text(output.get(field, ""))

    return output


def _extract_score(text: str, label: str) -> Optional[float]:
    patterns = [
        rf'"{label}"\s*:\s*([0-9]+(?:\.[0-9]+)?)',
        rf"{label}\s*[:：]\s*([0-9]+(?:\.[0-9]+)?)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            return _clamp_score(m.group(1))
    return None


def _extract_list_by_heading(text: str, heading: str) -> list[str]:
    pattern = (
        rf"{heading}[\s\S]{{0,120}}?(?:\n|\r\n)([\s\S]{{0,600}}?)(?:\n\n|###|####|$)"
    )
    m = re.search(pattern, text, flags=re.IGNORECASE)
    if not m:
        return []
    block = m.group(1)
    items = re.findall(r"(?:^|\n)\s*(?:[-*]|\d+\.)\s*(.+)", block)
    return [i.strip() for i in items if i.strip()][:6]


def _fallback_struct_from_text(text: str) -> dict[str, Any]:
    output = dict(_DEFAULT_HOOK_ANALYSIS)

    for field in _SCORE_FIELDS:
        score = _extract_score(text, field)
        if score is not None:
            output[field] = score

    # 中文字段提取（优先级高于英文，覆盖上方英文提取结果）
    # 匹配 "视觉冲击力: 7.2/10" 或 "视觉冲击力：7.2" 等格式
    for field, zh_label in _ZH_SCORE_MAPPINGS.items():
        m = re.search(rf"{zh_label}\s*[:：]\s*([0-9]+(?:\.[0-9]+)?)", text)
        if m:
            output[field] = _clamp_score(m.group(1))

    zh_score = re.search(r"综合评分\s*[:：]\s*([0-9]+(?:\.[0-9]+)?)", text)
    if zh_score:
        output["overall_score"] = _clamp_score(zh_score.group(1))

    output["strengths"] = _extract_list_by_heading(text, r"(?:亮点|优点|strengths)")
    output["weaknesses"] = _extract_list_by_heading(text, r"(?:待改进|不足|weaknesses)")
    output["suggestions"] = _extract_list_by_heading(
        text, r"(?:优化建议|建议|suggestions)"
    )

    # 精确提取各维度 comment（从对应标题后的段落/引用块提取，不再用整段文本回填）
    for field, zh_label in _ZH_COMMENT_MAPPINGS.items():
        m = re.search(
            rf"#{{1,4}}\s*{zh_label}.*?(?:\n)([\s\S]{{0,500}}?)(?=#{{1,4}}|\Z)",
            text,
            flags=re.IGNORECASE,
        )
        if m:
            # 去除 Markdown 引用符号 > 和多余空白
            comment = re.sub(r"^[>\s]+", "", m.group(1), flags=re.MULTILINE).strip()
            if comment:
                output[field] = _safe_text(comment, max_len=500)

    # 元信息字段提取（hook_type / target_audience / retention_prediction）
    for field, pattern in [
        ("hook_type", r"钩子类型\s*[:\uff1a*]+\s*(.+?)(?:[|｜]|\n|$)"),
        ("target_audience", r"目标受众\s*[:\uff1a*]+\s*(.+?)(?:[|｜]|\n|$)"),
        ("retention_prediction", r"留存预测\s*[:\uff1a*]+\s*(.+?)(?:\n\n|\Z)"),
    ]:
        m = re.search(pattern, text)
        if m:
            value = m.group(1).strip()
            if value:
                output[field] = _safe_text(value, max_len=200)

    return _normalize_output(output)


def _build_hook_markdown_summary(output: dict[str, Any]) -> str:
    overall = output.get("overall_score", 0)
    hook_type = output.get("hook_type", "未知")
    retention = output.get("retention_prediction", "N/A")
    audience = output.get("target_audience", "")

    def _score_line(name: str, score_key: str, comment_key: str) -> str:
        score = output.get(score_key, 0)
        comment = str(output.get(comment_key, "") or "").strip() or "暂无详细说明"
        return f"#### {name}: {score}/10\n> {comment}"

    strengths = _coerce_to_list(output.get("strengths"))
    weaknesses = _coerce_to_list(output.get("weaknesses"))
    suggestions = _coerce_to_list(output.get("suggestions"))

    strengths_text = "\n".join(f"- {s}" for s in strengths) if strengths else "- 暂无"
    weaknesses_text = (
        "\n".join(f"- {w}" for w in weaknesses) if weaknesses else "- 暂无"
    )
    suggestions_text = (
        "\n".join(f"{i + 1}. {s}" for i, s in enumerate(suggestions))
        if suggestions
        else "1. 暂无"
    )
    audience_line = f"\n- **目标受众**: {audience}" if audience else ""

    return (
        "## 前三秒钩子分析\n\n"
        f"### 综合评分: {overall}/10\n"
        f"- **钩子类型**: {hook_type}{audience_line}\n"
        f"- **留存预测**: {retention}\n\n"
        "---\n\n"
        "### 五维评分详情\n\n"
        f"{_score_line('视觉冲击力', 'visual_impact', 'visual_comment')}\n\n"
        f"{_score_line('语言钩子', 'language_hook', 'language_comment')}\n\n"
        f"{_score_line('情绪唤起', 'emotion_trigger', 'emotion_comment')}\n\n"
        f"{_score_line('信息密度', 'information_density', 'info_comment')}\n\n"
        f"{_score_line('节奏掌控', 'rhythm_control', 'rhythm_comment')}\n\n"
        "---\n\n"
        f"### 亮点\n{strengths_text}\n\n"
        f"### 待改进\n{weaknesses_text}\n\n"
        f"### 优化建议\n{suggestions_text}"
    )


def soft_fix_hook_output(
    *,
    callback_context: CallbackContext,
    llm_response: LlmResponse,
    model_response_event: Optional[Event] = None,
) -> Optional[LlmResponse]:
    agent_name = _agent_name(callback_context)
    if agent_name not in _TARGET_AGENTS:
        return llm_response

    if not llm_response or not llm_response.content or not llm_response.content.parts:
        return llm_response

    # 放行 function_call / function_response，避免干扰 SDK 事件追踪。
    # 必须检查所有 parts：当 parts[0]=文本、parts[1]=function_call 时，
    # 若只检查 parts[0] 会错误地改写文本，同时放行 function_call，导致死循环。
    for part in llm_response.content.parts:
        if hasattr(part, "function_call") and part.function_call:
            return llm_response
        if hasattr(part, "function_response") and part.function_response:
            return llm_response

    text = _get_first_text(llm_response)
    if not text:
        return llm_response

    if _is_tool_call_turn(model_response_event, text):
        return llm_response

    state = getattr(callback_context, "state", None)
    candidate = _extract_json_candidate(text)

    parsed: Any = None
    json_error: Optional[str] = None
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as e:
        json_error = str(e)
        logger.debug(
            "[soft_fix_hook_output] json.loads failed, trying json_repair: %s (text_len=%d)",
            json_error,
            len(candidate),
        )
        try:
            parsed = json_repair.loads(candidate)
            logger.info(
                "[soft_fix_hook_output] json_repair succeeded for agent=%s", agent_name
            )
        except Exception as repair_error:
            logger.warning(
                "[soft_fix_hook_output] json_repair also failed for agent=%s: %s (original: %s)",
                agent_name,
                str(repair_error),
                json_error,
            )
            parsed = None

    if isinstance(parsed, list):
        parsed = parsed[0] if parsed else {}

    # 仅当解析结果是含钩子字段的有效 dict 时才使用 JSON 路径；
    # json_repair 对纯 Markdown 文本会返回 {}，若不加校验会导致全 0.0 默认值。
    if (
        isinstance(parsed, dict)
        and not _looks_like_tool_envelope(parsed)
        and _has_hook_fields(parsed)
    ):
        normalized = _normalize_output(parsed)
        logger.info(
            "[soft_fix_hook_output] normalized by json path agent=%s", agent_name
        )
    else:
        normalized = _fallback_struct_from_text(text)
        logger.warning(
            "[soft_fix_hook_output] fallback to text extraction agent=%s "
            "(parsed_keys=%s)",
            agent_name,
            list(parsed.keys()) if isinstance(parsed, dict) else type(parsed).__name__,
        )

    markdown_summary = _build_hook_markdown_summary(normalized)
    llm_response.content.parts[0].text = markdown_summary

    if isinstance(state, dict):
        state["hook_analysis_struct"] = normalized
        state["hook_analysis"] = normalized
        state["hook_analysis_markdown"] = markdown_summary

    return llm_response
