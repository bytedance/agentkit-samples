"""
格式化Hook函数 - 修复输出格式错误
参考: multimedia项目的format_hook.py和video_breakdown_agent/hook/format_hook.py
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.events import Event
from google.adk.models import LlmResponse

logger = logging.getLogger(__name__)


def fix_prompt_output(
    *,
    callback_context: CallbackContext,
    llm_response: LlmResponse,
    model_response_event: Optional[Event] = None,
) -> Optional[LlmResponse]:
    """
    修复JSON格式错误，确保符合VideoPromptList schema

    Args:
        callback_context: 回调上下文
        llm_response: LLM响应对象
        model_response_event: 模型响应事件（可选）

    Returns:
        修复后的响应（或None表示不修改）
    """
    try:
        # 获取响应文本
        if (
            not llm_response
            or not llm_response.content
            or not llm_response.content.parts
        ):
            return llm_response

        # 放行 function_call / function_response，避免干扰 SDK 事件追踪
        part = llm_response.content.parts[0]
        if hasattr(part, "function_call") and part.function_call:
            return llm_response
        if hasattr(part, "function_response") and part.function_response:
            return llm_response

        response_text = str(part.text or "")
        if not response_text:
            return llm_response

        # 尝试解析JSON
        parsed = json.loads(response_text)

        # 验证必需字段
        if "prompts" not in parsed:
            logger.warning("输出缺少prompts字段，尝试修复")
            parsed = {"prompts": [], **parsed}

        if not isinstance(parsed["prompts"], list):
            logger.warning("prompts不是列表，尝试修复")
            parsed["prompts"] = []

        # 确保统计字段存在
        if "total_count" not in parsed:
            parsed["total_count"] = len(parsed["prompts"])

        if "total_selected" not in parsed:
            parsed["total_selected"] = sum(
                1 for p in parsed["prompts"] if p.get("selected", False)
            )

        if "total_cost" not in parsed:
            parsed["total_cost"] = sum(
                p.get("estimated_cost", 0)
                for p in parsed["prompts"]
                if p.get("selected", False)
            )

        # 重新序列化并更新响应
        llm_response.content.parts[0].text = json.dumps(
            parsed, ensure_ascii=False, indent=2
        )
        return llm_response

    except json.JSONDecodeError as e:
        logger.error(f"JSON解析失败: {e}")
        # 尝试提取JSON部分
        json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if json_match:
            try:
                extracted = json_match.group(0)
                parsed = json.loads(extracted)
                llm_response.content.parts[0].text = json.dumps(
                    parsed, ensure_ascii=False
                )
                return llm_response
            except Exception:
                pass

        # 无法修复，返回原响应
        return llm_response

    except Exception as e:
        logger.error(f"修复提示词输出失败: {e}")
        return llm_response


def fix_video_output(
    *,
    callback_context: CallbackContext,
    llm_response: LlmResponse,
    model_response_event: Optional[Event] = None,
) -> Optional[LlmResponse]:
    """
    修复JSON格式错误，确保符合VideoGenerationResult schema

    Args:
        callback_context: 回调上下文
        llm_response: LLM响应对象
        model_response_event: 模型响应事件（可选）

    Returns:
        修复后的响应（或None表示不修改）
    """
    try:
        # 获取响应文本
        if (
            not llm_response
            or not llm_response.content
            or not llm_response.content.parts
        ):
            return llm_response

        # 放行 function_call / function_response，避免干扰 SDK 事件追踪
        part = llm_response.content.parts[0]
        if hasattr(part, "function_call") and part.function_call:
            return llm_response
        if hasattr(part, "function_response") and part.function_response:
            return llm_response

        response_text = str(part.text or "")
        if not response_text:
            return llm_response

        parsed = json.loads(response_text)

        # 验证必需字段
        if "status" not in parsed:
            parsed["status"] = "unknown"

        if "generated_videos" not in parsed:
            parsed["generated_videos"] = []

        if "error_list" not in parsed:
            parsed["error_list"] = []

        # 统计字段
        if "total_requested" not in parsed:
            parsed["total_requested"] = len(parsed["generated_videos"]) + len(
                parsed["error_list"]
            )

        if "total_succeeded" not in parsed:
            parsed["total_succeeded"] = len(parsed["generated_videos"])

        if "total_failed" not in parsed:
            parsed["total_failed"] = len(parsed["error_list"])

        # 更新响应
        llm_response.content.parts[0].text = json.dumps(
            parsed, ensure_ascii=False, indent=2
        )
        return llm_response

    except Exception as e:
        logger.error(f"修复视频输出失败: {e}")
        return llm_response
