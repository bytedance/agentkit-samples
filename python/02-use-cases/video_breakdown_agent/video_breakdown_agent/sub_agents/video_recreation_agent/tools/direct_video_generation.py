"""
直接视频生成工具 - 解析用户提供的提示词，准备视频生成参数
用于场景：用户已有提示词，明确要求"生成视频"，无需重新拆解

核心原则：
1. 仅负责解析和准备数据（不执行视频生成）
2. 视频生成由后续的 video_generator_agent 自动执行
3. 灵活处理部分分镜数据
"""

from __future__ import annotations

import logging
import re
from typing import Dict, Optional

from google.adk.tools import ToolContext

logger = logging.getLogger(__name__)


def _resolve_frame_url(
    url: Optional[str],
    segment_index: int,
    tool_context,
) -> Optional[str]:
    """
    将 first_frame_url 参数解析为真实可用的图片 URL。

    处理三种情况：
    1. 合法 HTTP/HTTPS URL → 直接返回
    2. base64 data URL（data:image/...） → 直接返回（后续由 _upload_base64_to_tos 处理）
    3. 占位符文字 / None / 空字符串 → 从 session.state["process_video_result"] 按
       segment_index 查找并返回第一帧真实 URL；若找不到则返回 None（退化为纯文生视频）
    """
    # 情况 1 & 2：已经是合法 URL
    if url and (
        url.startswith("http://")
        or url.startswith("https://")
        or url.startswith("data:image/")
    ):
        logger.info(f"[_resolve_frame_url] 使用传入的有效帧 URL（前缀：{url[:30]}...）")
        return url

    # 情况 3：占位符 / None → 从 session state 回查真实帧
    if url:
        logger.info(
            f"[_resolve_frame_url] 检测到无效 URL（占位符）：{url[:60]}，将从 session state 回查"
        )
    else:
        logger.info(
            f"[_resolve_frame_url] first_frame_url 为空，将从 session state 回查 segment {segment_index} 的帧"
        )

    process_result = tool_context.state.get("process_video_result", {})
    segments = process_result.get("segments", [])

    for seg in segments:
        if seg.get("index") == segment_index:
            frame_urls = seg.get("frame_urls", [])
            # 过滤掉占位符，只取真实 URL
            valid = [
                u
                for u in frame_urls
                if u and (u.startswith("http") or u.startswith("data:image/"))
            ]
            if valid:
                logger.info(
                    f"[_resolve_frame_url] 找到 segment {segment_index} 的真实帧 URL "
                    f"（共 {len(valid)} 张，取第一张，前缀：{valid[0][:30]}...）"
                )
                return valid[0]
            else:
                logger.warning(
                    f"[_resolve_frame_url] segment {segment_index} 无可用帧 URL（frame_urls={frame_urls}）"
                )
                return None

    logger.warning(
        f"[_resolve_frame_url] 未找到 segment_index={segment_index} 的分镜数据，退化为 t2v"
    )
    return None


def parse_segment_info(user_message: str) -> Dict:
    """
    从用户消息中智能解析分镜信息

    Args:
        user_message: 用户输入的文本

    Returns:
        解析出的信息字典
    """
    info = {
        "segment_name": "分镜1",
        "segment_index": 1,
        "start_time": 0.0,
        "end_time": 5.0,
        "duration": 5,
        "positive_prompt": "",
        "negative_prompt": "",
        "ratio": "16:9",
    }

    # 解析分镜编号：分镜4、segment 2、第3镜等
    segment_match = re.search(
        r"(?:分镜|segment|第)[\s]*(\d+)", user_message, re.IGNORECASE
    )
    if segment_match:
        segment_num = int(segment_match.group(1))
        info["segment_name"] = f"分镜{segment_num}"
        info["segment_index"] = segment_num

    # 解析时间段：(10.0-17.07s)、10s-17s等
    time_match = re.search(r"\(?([\d.]+)[\s]*-[\s]*([\d.]+)[s秒]?\)?", user_message)
    if time_match:
        start = float(time_match.group(1))
        end = float(time_match.group(2))
        info["start_time"] = start
        info["end_time"] = end
        info["duration"] = int(end - start)

    # 解析正向提示词
    positive_match = re.search(
        r"正向提示词[：:](.*?)(?=负向提示词|生成方式|$)",
        user_message,
        re.DOTALL | re.IGNORECASE,
    )
    if positive_match:
        info["positive_prompt"] = positive_match.group(1).strip()

    # 解析负向提示词
    negative_match = re.search(
        r"负向提示词[：:](.*?)(?=生成方式|预估|$)",
        user_message,
        re.DOTALL | re.IGNORECASE,
    )
    if negative_match:
        info["negative_prompt"] = negative_match.group(1).strip()

    # 解析比例：16:9、9:16等
    ratio_match = re.search(r"(\d+:\d+|adaptive)", user_message)
    if ratio_match:
        info["ratio"] = ratio_match.group(1)

    return info


async def direct_video_generation(
    tool_context: ToolContext,
    positive_prompt: Optional[str] = None,
    negative_prompt: Optional[str] = None,
    duration: Optional[int] = None,
    ratio: Optional[str] = None,
    segment_name: Optional[str] = None,
    generate_audio: bool = False,
    first_frame_url: Optional[str] = None,
) -> Dict:
    """
    解析用户提供的提示词，准备视频生成参数（不执行生成）

    适用场景：
    - 用户已有提示词，直接要求"生成视频"
    - 用户只提供部分分镜，不需要完整序列
    - 快速测试提示词效果

    核心原则：
    - 仅解析和准备数据，视频生成由后续Agent自动执行
    - 不强求完整数据，不浪费token
    - 自动从用户消息智能解析参数

    Args:
        tool_context: 工具上下文
        positive_prompt: 正向提示词（可选，会从用户消息解析）
        negative_prompt: 负向提示词（可选）
        duration: 视频时长（秒，可选）
        ratio: 宽高比（16:9/9:16/1:1/adaptive，可选）
        segment_name: 分镜名称（可选）
        generate_audio: 是否生成音频
        first_frame_url: 首帧图片URL（可选）

    Returns:
        {
            "status": "success" | "error",
            "message": str,
            "segment_name": str,
            "prepared": bool
        }
    """
    try:
        # ── 优先复用已有 pending_prompts（适用于"用这个提示词生成视频"场景）──────────
        # 当用户说"用这个提示词生成同款视频"时，user_message 里不含提示词文本，
        # 但上一轮 generate_video_prompts 已将提示词写入 pending_prompts。
        # 此时直接复用，重置 selected=True，跳过 user_message 解析。
        existing_pending = tool_context.state.get("pending_prompts")
        if not positive_prompt and existing_pending:
            existing_prompts = existing_pending.get("prompts", [])
            valid_prompts = [
                p for p in existing_prompts if p.get("positive_prompt", "").strip()
            ]
            if valid_prompts:
                # 重新启用所有有效提示词（之前可能被 video_generate 重置为 selected=False）
                for p in valid_prompts:
                    p["selected"] = True
                tool_context.state["pending_prompts"] = {
                    **existing_pending,
                    "prompts": existing_prompts,
                    "total_selected": len(valid_prompts),
                }
                names = ", ".join(p.get("segment_name", "") for p in valid_prompts)
                logger.info(
                    f"[direct_video_generation] 复用已有 pending_prompts: {names}"
                )
                return {
                    "status": "success",
                    "message": f"✅ 已复用上一次生成的提示词（{names}），即将生成视频",
                    "segment_name": valid_prompts[0].get("segment_name", ""),
                    "prompt_length": len(valid_prompts[0].get("positive_prompt", "")),
                    "estimated_cost": sum(
                        p.get("estimated_cost", 0.7) for p in valid_prompts
                    ),
                    "prepared": True,
                }
        # ────────────────────────────────────────────────────────────────────────────

        # 获取用户原始消息
        user_message = tool_context.state.get("user_message", "")

        logger.info(f"提示词准备工具被调用，用户消息长度={len(user_message)}")

        # 智能解析用户消息中的分镜信息
        parsed_info = parse_segment_info(user_message)

        # 参数优先级：显式参数 > 解析参数 > 默认值
        final_positive = positive_prompt or parsed_info["positive_prompt"]
        final_negative = (
            negative_prompt
            or parsed_info["negative_prompt"]
            or "模糊画面、不连贯、质量差"
        )
        final_duration = duration or parsed_info["duration"]
        final_ratio = ratio or parsed_info["ratio"]
        final_segment_name = segment_name or parsed_info["segment_name"]

        # 验证必填参数
        if not final_positive:
            return {
                "status": "error",
                "message": "未找到有效的正向提示词，请提供提示词内容",
                "segment_name": final_segment_name,
                "prepared": False,
            }

        logger.info(
            f"解析结果: {final_segment_name}，时长={final_duration}s，提示词长度={len(final_positive)}"
        )

        # 解析首帧 URL（自动处理占位符 → 从 session state 回查真实帧）
        resolved_frame = _resolve_frame_url(
            first_frame_url,
            parsed_info["segment_index"],
            tool_context,
        )
        if resolved_frame:
            logger.info("[direct_video_generation] 首帧已解析，将使用 i2v 模式")
        else:
            logger.info("[direct_video_generation] 无可用首帧，将使用 t2v 模式")

        # 构建标准的提示词数据结构
        prompt_data = {
            "segment_index": parsed_info["segment_index"],
            "segment_name": final_segment_name,
            "start_time": parsed_info["start_time"],
            "end_time": parsed_info["end_time"],
            "positive_prompt": final_positive,
            "negative_prompt": final_negative,
            "duration": final_duration,
            "ratio": final_ratio,
            "estimated_cost": 0.7,  # 单个视频预估费用
            "selected": True,  # 标记为选中
            "generate_audio": generate_audio,
            "first_frame": resolved_frame,  # 已校验的真实 URL（None = 退化为 t2v）
        }

        # 将提示词数据存入session state（供后续video_generator_agent读取）
        tool_context.state["pending_prompts"] = {
            "prompts": [prompt_data],
            "total_cost": 0.7,
            "total_selected": 1,
        }

        logger.info(f"✅ 提示词已准备完毕: {final_segment_name}，等待后续视频生成")

        return {
            "status": "success",
            "message": f"✅ {final_segment_name} 已准备完毕！\n\n"
            f"📊 生成信息：\n"
            f"  - 时间段：{parsed_info['start_time']:.1f}-{parsed_info['end_time']:.1f}秒\n"
            f"  - 时长：{final_duration}秒\n"
            f"  - 预估费用：¥0.70",
            "segment_name": final_segment_name,
            "prompt_length": len(final_positive),
            "estimated_cost": 0.7,
            "prepared": True,
        }

    except Exception as e:
        logger.error(f"提示词解析失败: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"解析失败: {str(e)}",
            "segment_name": "",
            "prepared": False,
        }
