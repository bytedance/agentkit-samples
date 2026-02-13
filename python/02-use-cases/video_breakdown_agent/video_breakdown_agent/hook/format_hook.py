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

_TARGET_AGENTS = {"hook_format_agent", "hook_analyzer_agent"}
_MAX_COMMENT_LEN = 800

_SCORE_FIELDS = (
    "overall_score",
    "visual_impact",
    "language_hook",
    "emotion_trigger",
    "information_density",
    "rhythm_control",
)

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
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, flags=re.IGNORECASE)
    if fenced and fenced.group(1).strip():
        return fenced.group(1).strip()
    return text.strip()


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

    zh_score = re.search(r"综合评分\s*[:：]\s*([0-9]+(?:\.[0-9]+)?)", text)
    if zh_score:
        output["overall_score"] = _clamp_score(zh_score.group(1))

    output["strengths"] = _extract_list_by_heading(text, r"(?:亮点|优点|strengths)")
    output["weaknesses"] = _extract_list_by_heading(text, r"(?:待改进|不足|weaknesses)")
    output["suggestions"] = _extract_list_by_heading(
        text, r"(?:优化建议|建议|suggestions)"
    )

    excerpt = _safe_text(text, max_len=500)
    if excerpt:
        for field in (
            "visual_comment",
            "language_comment",
            "emotion_comment",
            "info_comment",
            "rhythm_comment",
        ):
            output[field] = excerpt

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

    text = _get_first_text(llm_response)
    if not text:
        return llm_response

    if _is_tool_call_turn(model_response_event, text):
        return llm_response

    state = getattr(callback_context, "state", None)
    candidate = _extract_json_candidate(text)

    parsed: Any = None
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        try:
            parsed = json_repair.loads(candidate)
        except Exception:
            parsed = None

    if isinstance(parsed, list):
        parsed = parsed[0] if parsed else {}

    if isinstance(parsed, dict) and not _looks_like_tool_envelope(parsed):
        normalized = _normalize_output(parsed)
        logger.info(
            "[soft_fix_hook_output] normalized by json path agent=%s", agent_name
        )
    else:
        normalized = _fallback_struct_from_text(text)
        logger.warning(
            "[soft_fix_hook_output] fallback to text extraction agent=%s", agent_name
        )

    markdown_summary = _build_hook_markdown_summary(normalized)
    llm_response.content.parts[0].text = markdown_summary

    if isinstance(state, dict):
        state["hook_analysis_struct"] = normalized
        state["hook_analysis"] = normalized
        state["hook_analysis_markdown"] = markdown_summary

    return llm_response
