"""
人工审核界面工具 - 展示生成的提示词供用户选择和修改
参考Plan中的渐进式分镜选择生成机制
"""

from __future__ import annotations

import logging
from typing import Dict, List

from google.adk.tools import ToolContext

logger = logging.getLogger(__name__)


def format_prompt_preview(prompts: List[Dict]) -> str:
    """
    格式化提示词为Markdown预览

    Args:
        prompts: 提示词列表

    Returns:
        格式化的Markdown字符串
    """
    total_count = len(prompts)
    selected_count = sum(1 for p in prompts if p.get("selected", False))
    total_cost = sum(
        p.get("estimated_cost", 0) for p in prompts if p.get("selected", False)
    )
    total_duration = sum(
        p.get("duration", 0) for p in prompts if p.get("selected", False)
    )

    markdown_parts = [
        "## 📝 视频生成提示词预览\n",
        f"> 💡 **成本提示**: 共{total_count}个分镜，当前选中{selected_count}个，预估费用¥{total_cost:.2f}元\n",
        f"> ⏱️ **时长**: {total_duration:.1f}秒\n\n",
    ]

    # 逐个分镜展示
    for prompt_data in prompts:
        segment_index = prompt_data.get("segment_index", 0)
        start_time = prompt_data.get("start_time", 0)
        end_time = prompt_data.get("end_time", 0)
        duration = prompt_data.get("duration", 0)
        positive_prompt = prompt_data.get("positive_prompt", "")
        negative_prompt = prompt_data.get("negative_prompt", "")
        estimated_cost = prompt_data.get("estimated_cost", 0)
        selected = prompt_data.get("selected", False)

        # 标题行（带选中状态）
        checkbox = "☑️" if selected else "☐"
        highlight = (
            " - **默认选中（前3秒黄金钩子）** ⭐"
            if segment_index == 1 and selected
            else ""
        )

        markdown_parts.append(
            f"### {checkbox} 分镜{segment_index} ({start_time:.1f}-{end_time:.1f}秒){highlight}\n\n"
        )

        # 提示词内容
        markdown_parts.append(f"**正向提示词**: {positive_prompt}\n\n")
        markdown_parts.append(f"**负向提示词**: {negative_prompt}\n\n")

        # 元数据
        markdown_parts.append(
            f"**预估时长**: {duration:.1f}秒 | **预估费用**: ¥{estimated_cost:.2f}元\n\n"
        )

        # 参考帧（如果有）
        first_frame = prompt_data.get("first_frame")
        if first_frame:
            markdown_parts.append(f"**参考帧**: ![参考帧]({first_frame})\n\n")

        markdown_parts.append("---\n\n")

    # 操作指令
    markdown_parts.extend(
        [
            "## ✏️ 操作指令\n\n",
            "### 选择分镜\n",
            "- 选择多个分镜: `选择分镜1,2,4` 或 `增加分镜2和3`\n",
            "- 全选: `生成全部分镜`\n",
            "- 只选一个: `只生成分镜1`\n\n",
            "### 修改提示词\n",
            "- 修改指定分镜: `修改分镜1提示词为：[新提示词]`\n",
            "- 示例: `修改分镜2为：换成浅粉色手机壳，强调轻薄设计`\n\n",
            "### 确认生成\n",
            "- 确认当前选择: `确认生成` 或 `开始生成`\n\n",
            "## 💡 推荐策略\n\n",
            "- **快速测试**: 只生成分镜1（前3秒钩子，效果验证）\n",
            "- **完整复刻**: 选择全部分镜\n",
            "- **精华复刻**: 选择分镜1+关键高潮分镜\n",
            "- **渐进式生成**: 先生成1个测试 → 满意后追加其他\n\n",
        ]
    )

    return "".join(markdown_parts)


async def review_prompts(tool_context: ToolContext) -> Dict:
    """
    人工审核界面工具

    展示生成的提示词列表，供用户选择要生成的分镜和修改提示词。
    默认只选中分镜1（前3秒黄金钩子），降低首次尝试成本。

    Args:
        tool_context: 工具上下文

    Returns:
        {
            "status": "success" | "error",
            "preview_markdown": str,  # 格式化的Markdown预览
            "total_count": int,       # 总分镜数
            "selected_count": int,    # 已选中数量
            "total_cost": float,      # 预估总费用
            "message": str,
            "awaiting_user_action": bool  # 等待用户操作
        }
    """
    try:
        # 读取待审核的提示词
        pending_prompts = tool_context.state.get("pending_prompts")

        if not pending_prompts:
            return {
                "status": "error",
                "message": "未找到待审核的提示词，请先生成提示词",
                "preview_markdown": "",
                "total_count": 0,
                "selected_count": 0,
                "total_cost": 0.0,
                "awaiting_user_action": False,
            }

        prompts = pending_prompts.get("prompts", [])

        if not prompts:
            return {
                "status": "error",
                "message": "提示词列表为空",
                "preview_markdown": "",
                "total_count": 0,
                "selected_count": 0,
                "total_cost": 0.0,
                "awaiting_user_action": False,
            }

        logger.info(f"展示提示词审核界面，共{len(prompts)}个分镜")

        # 格式化为Markdown
        preview_markdown = format_prompt_preview(prompts)

        # 统计信息
        total_count = len(prompts)
        selected_count = sum(1 for p in prompts if p.get("selected", False))
        total_cost = sum(
            p.get("estimated_cost", 0) for p in prompts if p.get("selected", False)
        )

        logger.info(
            f"当前选中{selected_count}/{total_count}个分镜，预估费用¥{total_cost:.2f}元"
        )

        return {
            "status": "success",
            "preview_markdown": preview_markdown,
            "total_count": total_count,
            "selected_count": selected_count,
            "total_cost": total_cost,
            "message": f"提示词预览已生成，当前选中{selected_count}个分镜，等待用户确认",
            "awaiting_user_action": True,  # 标记等待用户操作
        }

    except Exception as e:
        logger.error(f"展示提示词失败: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"展示提示词失败: {str(e)}",
            "preview_markdown": "",
            "total_count": 0,
            "selected_count": 0,
            "total_cost": 0.0,
            "awaiting_user_action": False,
        }
