"""
分镜选择Hook - 处理用户的分镜选择指令
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.genai import types

logger = logging.getLogger(__name__)


def hook_segment_selection(
    callback_context: CallbackContext,
) -> Optional[types.Content]:
    """
    解析用户的分镜选择指令，更新session.state

    支持的指令格式：
    - "选择分镜1,2,4"
    - "增加分镜2和3"
    - "只生成分镜1"
    - "生成全部分镜"

    Args:
        callback_context: 回调上下文（包含session和user_content）

    Returns:
        None (不修改用户输入)
    """
    try:
        # 获取用户输入文本
        user_content = callback_context.user_content
        if not user_content or not user_content.parts:
            return None

        query = ""
        for part in user_content.parts:
            if part.text:
                query += part.text

        if not query:
            return None

        # 获取session
        session = callback_context.session
        if not session or not hasattr(session, "state"):
            return None

        # 存储用户消息供 direct_video_generation 工具使用
        session.state["user_message"] = query
        logger.info(f"已存储用户消息: {len(query)} 字符")

        # 读取pending_prompts
        pending_prompts = session.state.get("pending_prompts")
        if not pending_prompts:
            return None

        prompts = pending_prompts.get("prompts", [])
        if not prompts:
            return None

        # 检测选择指令
        selection_updated = False

        # 模式1: "选择分镜1,2,4" 或 "增加分镜2和3"
        pattern1 = r"(?:选择|增加|添加).*?分镜\s*([0-9,，、和\s]+)"
        match1 = re.search(pattern1, query)

        if match1:
            # 提取分镜索引
            segments_str = match1.group(1)
            # 替换中文标点和"和"
            segments_str = (
                segments_str.replace("，", ",")
                .replace("、", ",")
                .replace("和", ",")
                .replace(" ", "")
            )
            segment_indices = [
                int(x.strip()) for x in segments_str.split(",") if x.strip().isdigit()
            ]

            if segment_indices:
                logger.info(f"用户选择分镜: {segment_indices}")

                # 更新选中状态
                for prompt_data in prompts:
                    if prompt_data["segment_index"] in segment_indices:
                        prompt_data["selected"] = True

                selection_updated = True

        # 模式2: "只生成分镜X"
        pattern2 = r"只.*?生成.*?分镜\s*(\d+)"
        match2 = re.search(pattern2, query)

        if match2:
            segment_index = int(match2.group(1))
            logger.info(f"用户只选择分镜: {segment_index}")

            # 取消所有选中，只选中指定分镜
            for prompt_data in prompts:
                prompt_data["selected"] = prompt_data["segment_index"] == segment_index

            selection_updated = True

        # 模式3: "生成全部分镜"
        if re.search(r"生成.*?全部|全部.*?生成|生成.*?所有", query):
            logger.info("用户选择全部分镜")

            # 选中所有分镜
            for prompt_data in prompts:
                prompt_data["selected"] = True

            selection_updated = True

        # 如果更新了选择，重新计算统计数据
        if selection_updated:
            pending_prompts["prompts"] = prompts
            pending_prompts["total_selected"] = sum(
                1 for p in prompts if p.get("selected", False)
            )
            pending_prompts["total_cost"] = sum(
                p.get("estimated_cost", 0) for p in prompts if p.get("selected", False)
            )
            pending_prompts["total_duration"] = sum(
                p.get("duration", 0) for p in prompts if p.get("selected", False)
            )

            session.state["pending_prompts"] = pending_prompts

            logger.info(
                f"分镜选择已更新: 选中{pending_prompts['total_selected']}/{len(prompts)}个"
            )

        return None  # 不修改用户输入

    except Exception as e:
        logger.error(f"处理分镜选择失败: {e}")
        return None
