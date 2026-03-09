"""
风格迁移工具 - 支持产品/场景替换，保留镜头语言
参考Plan中的风格迁移模块设计
"""

from __future__ import annotations

import logging
import re
from typing import Dict, Optional

from google.adk.tools import ToolContext
from video_breakdown_agent.utils.doubao_client import (
    call_doubao_vision,
)  # 复用现有LLM调用

logger = logging.getLogger(__name__)


def smart_replace_keywords(
    original_prompt: str,
    replacements: Dict[str, str],
    preserve_camera: bool = True,
    preserve_lighting: bool = True,
) -> str:
    """
    智能替换提示词中的关键元素

    Args:
        original_prompt: 原始提示词
        replacements: 替换映射 {"原产品": "新产品", "原场景": "新场景"}
        preserve_camera: 保留镜头语言
        preserve_lighting: 保留光影描述

    Returns:
        替换后的提示词
    """
    new_prompt = original_prompt

    # 执行关键词替换
    for old_text, new_text in replacements.items():
        # 使用正则表达式，确保完整词匹配
        pattern = re.compile(re.escape(old_text), re.IGNORECASE)
        new_prompt = pattern.sub(new_text, new_prompt)

    # 如果需要，确保镜头语言保留
    if preserve_camera:
        camera_keywords = [
            "镜头",
            "特写",
            "中景",
            "全景",
            "环绕",
            "推进",
            "拉远",
            "跟拍",
            "手持",
            "固定机位",
        ]
        # 检查镜头关键词是否仍然存在
        has_camera = any(keyword in new_prompt for keyword in camera_keywords)
        if not has_camera and any(
            keyword in original_prompt for keyword in camera_keywords
        ):
            # 从原提示词中提取镜头描述并附加
            for keyword in camera_keywords:
                if keyword in original_prompt:
                    # 提取包含该关键词的短语
                    match = re.search(rf"([^，。]+{keyword}[^，。]+)", original_prompt)
                    if match:
                        camera_phrase = match.group(1)
                        if camera_phrase not in new_prompt:
                            new_prompt += f"，{camera_phrase}"
                        break

    return new_prompt


async def llm_assisted_transfer(
    original_prompt: str, transfer_config: Dict, tool_context: ToolContext
) -> str:
    """
    使用LLM辅助风格迁移（更智能）

    Args:
        original_prompt: 原始提示词
        transfer_config: 迁移配置
        tool_context: 工具上下文（用于LLM调用）

    Returns:
        LLM生成的新提示词
    """
    original_product = transfer_config.get("original_product", "原产品")
    target_product = transfer_config.get("target_product", "新产品")
    preserve_camera = transfer_config.get("preserve_camera", True)
    preserve_lighting = transfer_config.get("preserve_lighting", True)
    new_background = transfer_config.get("new_background")

    # 构建LLM提示词
    system_instruction = """
你是专业的视频提示词工程师。你的任务是进行风格迁移：
保留原提示词的镜头语言、光影氛围和节奏，仅替换产品和场景元素。

输出要求：
1. 保持原提示词的电影级结构（时间+场景+人物动作+镜头语言+光影+风格+节奏）
2. 仅替换产品相关描述
3. 保留所有镜头运动描述（如"镜头缓慢推进"、"环绕旋转"等）
4. 保留光影描述（如"柔和暖光"、"侧光勾勒"等）
5. 输出纯文本提示词，不要添加解释
"""

    user_message = f"""
原始提示词：
{original_prompt}

迁移任务：
- 原产品：{original_product}
- 新产品：{target_product}
"""

    if new_background:
        user_message += f"- 新背景：{new_background}\n"

    if preserve_camera:
        user_message += "- 必须保留：所有镜头语言描述\n"

    if preserve_lighting:
        user_message += "- 必须保留：所有光影氛围描述\n"

    user_message += "\n请输出迁移后的提示词："

    try:
        # 调用LLM（复用现有的doubao_client）
        response = await call_doubao_vision(
            model_name="doubao-seed",  # 使用主推理模型
            system_instruction=system_instruction,
            prompt=user_message,
            images=[],  # 纯文本任务，无需图片
        )

        # 提取响应文本
        new_prompt = response.strip()

        # 验证：确保关键元素被保留
        if preserve_camera and "镜头" not in new_prompt and "镜头" in original_prompt:
            logger.warning("LLM输出缺少镜头描述，回退到规则替换")
            return smart_replace_keywords(
                original_prompt, {original_product: target_product}
            )

        return new_prompt

    except Exception as e:
        logger.error(f"LLM辅助迁移失败: {e}，回退到规则替换")
        # 降级到规则替换
        return smart_replace_keywords(
            original_prompt, {original_product: target_product}
        )


async def style_transfer(
    tool_context: ToolContext,
    original_product: str,
    target_product: str,
    preserve_camera: bool = True,
    preserve_lighting: bool = True,
    new_background: Optional[str] = None,
    use_llm_enhancement: bool = True,
) -> Dict:
    """
    风格迁移工具

    将已生成的提示词进行风格迁移，替换产品/场景，保留镜头语言和氛围。

    Args:
        tool_context: 工具上下文
        original_product: 原产品描述（如"水杯"）
        target_product: 目标产品描述（如"手机壳"）
        preserve_camera: 是否保留镜头语言（默认True）
        preserve_lighting: 是否保留光影风格（默认True）
        new_background: 新背景描述（可选）
        use_llm_enhancement: 是否使用LLM智能增强（默认True）

    Returns:
        {
            "status": "success" | "error",
            "transferred_prompts": List[Dict],  # 迁移后的提示词列表
            "total_count": int,
            "message": str
        }
    """
    try:
        # 读取待处理的提示词
        pending_prompts = tool_context.state.get("pending_prompts")

        if not pending_prompts:
            return {
                "status": "error",
                "message": "未找到待迁移的提示词，请先生成提示词",
                "transferred_prompts": [],
                "total_count": 0,
            }

        prompts = pending_prompts.get("prompts", [])

        if not prompts:
            return {
                "status": "error",
                "message": "提示词列表为空",
                "transferred_prompts": [],
                "total_count": 0,
            }

        logger.info(f"开始风格迁移，共{len(prompts)}个分镜")
        logger.info(f"迁移任务：{original_product} → {target_product}")

        # 构建迁移配置
        transfer_config = {
            "original_product": original_product,
            "target_product": target_product,
            "preserve_camera": preserve_camera,
            "preserve_lighting": preserve_lighting,
            "new_background": new_background,
            "use_llm_enhancement": use_llm_enhancement,
        }

        # 逐个分镜进行迁移
        transferred_prompts = []

        for prompt_data in prompts:
            original_prompt = prompt_data.get("positive_prompt", "")

            if not original_prompt:
                logger.warning(f"分镜{prompt_data['segment_index']}缺少提示词，跳过")
                transferred_prompts.append(prompt_data)
                continue

            # 执行迁移
            if use_llm_enhancement:
                # 使用LLM智能迁移
                new_prompt = await llm_assisted_transfer(
                    original_prompt=original_prompt,
                    transfer_config=transfer_config,
                    tool_context=tool_context,
                )
            else:
                # 使用规则替换
                replacements = {original_product: target_product}
                if new_background:
                    # 尝试识别原背景并替换
                    # 简单策略：替换"背景"相关描述
                    if "背景" in original_prompt:
                        # 提取原背景描述
                        match = re.search(r"背景([^，。]+)", original_prompt)
                        if match:
                            old_bg = match.group(1)
                            replacements[f"背景{old_bg}"] = f"背景{new_background}"

                new_prompt = smart_replace_keywords(
                    original_prompt=original_prompt,
                    replacements=replacements,
                    preserve_camera=preserve_camera,
                    preserve_lighting=preserve_lighting,
                )

            # 更新提示词
            transferred_data = prompt_data.copy()
            transferred_data["positive_prompt"] = new_prompt
            transferred_data["style_transferred"] = True  # 标记已迁移

            transferred_prompts.append(transferred_data)

            logger.info(f"✅ 分镜{prompt_data['segment_index']}迁移完成")

        # 更新session state
        pending_prompts["prompts"] = transferred_prompts
        pending_prompts["style_transfer_enabled"] = True
        pending_prompts["transfer_config"] = transfer_config
        tool_context.state["pending_prompts"] = pending_prompts

        logger.info(f"✅ 风格迁移完成，共{len(transferred_prompts)}个分镜")

        return {
            "status": "success",
            "transferred_prompts": transferred_prompts,
            "total_count": len(transferred_prompts),
            "transfer_config": transfer_config,
            "message": f"成功迁移{len(transferred_prompts)}个分镜的提示词（{original_product} → {target_product}）",
        }

    except Exception as e:
        logger.error(f"风格迁移失败: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"风格迁移失败: {str(e)}",
            "transferred_prompts": [],
            "total_count": 0,
        }
