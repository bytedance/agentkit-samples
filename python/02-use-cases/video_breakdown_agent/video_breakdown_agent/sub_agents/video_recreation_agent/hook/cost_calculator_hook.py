"""
费用计算Hook - 计算和显示预估费用
"""

from __future__ import annotations

import logging

from google.adk.agents.callback_context import CallbackContext

logger = logging.getLogger(__name__)

# 费率配置（元/秒）
COST_PER_SECOND = 1.5  # 假设每秒1.5元


async def hook_cost_calculator(
    callback_context: CallbackContext,
):
    """
    计算预估费用，并在响应中添加费用提示

    注意：after_agent_callback 只接收 callback_context 参数，
    不像 after_model_callback 那样接收 llm_response

    Args:
        callback_context: 回调上下文（包含session）
    """
    try:
        # 获取session
        session = callback_context.session
        if not session or not hasattr(session, "state"):
            return

        # 读取pending_prompts
        pending_prompts = session.state.get("pending_prompts")
        if not pending_prompts:
            return

        prompts = pending_prompts.get("prompts", [])

        # 重新计算费用（确保准确）
        total_cost = 0.0
        selected_count = 0
        total_duration = 0.0

        for prompt_data in prompts:
            duration = prompt_data.get("duration", 0)
            selected = prompt_data.get("selected", False)

            # 更新预估费用
            estimated_cost = duration * COST_PER_SECOND
            prompt_data["estimated_cost"] = round(estimated_cost, 2)

            if selected:
                total_cost += estimated_cost
                selected_count += 1
                total_duration += duration

        # 更新session state
        pending_prompts["total_cost"] = round(total_cost, 2)
        pending_prompts["total_selected"] = selected_count
        pending_prompts["total_duration"] = round(total_duration, 1)
        session.state["pending_prompts"] = pending_prompts

        logger.info(
            f"费用计算完成: 选中{selected_count}个分镜，总时长{total_duration:.1f}秒，预估费用¥{total_cost:.2f}元"
        )

    except Exception as e:
        logger.error(f"费用计算失败: {e}")
