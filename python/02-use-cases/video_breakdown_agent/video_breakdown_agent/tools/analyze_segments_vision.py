"""
视觉分镜分析工具（自包含）
使用豆包官方 vision API 分析关键帧图片（/responses endpoint）

迁移来源: video-breakdown-master/app/services/gemini_service.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

from google.adk.tools import ToolContext
from video_breakdown_agent.utils.doubao_client import call_doubao_vision

logger = logging.getLogger(__name__)

# 功能标签枚举（来自 enhance_prompts.py）
FUNCTION_TAG_OPTIONS = [
    "强钩子",
    "痛点切入",
    "问题澄清",
    "解决方案",
    "产品介绍",
    "信任建立",
    "产品展示",
    "价值预告",
    "过渡",
    "价值输出",
    "成分深挖",
    "效果证明",
    "用户证言",
    "情感背书",
    "价值强化",
    "效果总结",
    "双重收益",
    "强CTA",
    "行动召唤",
]


def _build_segment_prompt(segment: Dict[str, Any]) -> Dict[str, Any]:
    """构造单个分镜的分析提示词 + JSON schema"""
    frame_count = len(segment.get("frame_urls", []))
    function_tags_str = "、".join(FUNCTION_TAG_OPTIONS)

    speech_hint = ""
    if segment.get("speech_text"):
        speech_hint = f"该片段的语音内容：「{segment['speech_text']}」"

    instruction = {
        "task": "请对这个视频片段进行综合分析，包括视觉分析、语音类型判断和内容标注",
        "segment_info": {
            "镜号": segment["index"],
            "起止时间": f"{segment['start']:.1f}s - {segment['end']:.1f}s",
            "时长": f"{(segment['end'] - segment['start']):.1f}s",
            "关键帧数量": frame_count,
            "帧说明": f"提供了{frame_count}张关键帧图片（时间均匀采样），请综合所有图片进行分析",
            "语音内容": speech_hint or "无语音内容",
        },
        "分析维度": {
            "视觉表现层": {
                "分析要点": [
                    "景别识别（特写/近景/中景/全景/远景）",
                    "运镜分析（固定/推拉/摇移/跟随/环绕等）",
                    "画面内容描述：必须综合所有关键帧，描述整个片段的画面内容",
                    "如果多张图片之间画面有变化，需要描述变化过程",
                    "如果画面基本一致，则描述画面的主要元素和场景",
                ]
            },
            "语音类型判断": {
                "判断标准": {
                    "口播": "画面中有人物的脸部清晰可见，且正在说话",
                    "旁白": "画面中没有人在说话，配合画外音",
                }
            },
            "内容标注": {
                "画面小标题": "根据画面内容，提炼≤10个汉字的核心要点标题",
                "内容标签": "根据语音内容（如有）或画面内容，提炼1-2个关键标签",
                "功能标签": f"识别该片段在视频叙事中的功能角色，从以下选项中选择1个最匹配的：{function_tags_str}",
            },
        },
        "输出要求": "必须输出结构化JSON，包含视觉分析和内容标注所有字段",
    }

    schema = {
        "name": "segment_comprehensive_analysis_schema",
        "schema": {
            "type": "object",
            "properties": {
                "视觉表现": {
                    "type": "object",
                    "properties": {
                        "景别": {
                            "type": "string",
                            "enum": ["特写", "近景", "中景", "全景", "远景"],
                        },
                        "运镜": {
                            "type": "string",
                            "enum": [
                                "固定",
                                "推镜",
                                "拉镜",
                                "摇镜",
                                "移镜",
                                "跟随",
                                "环绕",
                                "推拉",
                            ],
                        },
                        "画面内容": {"type": "string"},
                    },
                    "required": ["景别", "运镜", "画面内容"],
                },
                "语音类型": {"type": "string", "enum": ["口播", "旁白"]},
                "summary": {"type": "string"},
                "画面小标题": {
                    "type": "string",
                    "description": "画面核心要点，≤10个汉字",
                },
                "内容标签": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "1-2个内容关键标签",
                },
                "功能标签": {
                    "type": "string",
                    "enum": FUNCTION_TAG_OPTIONS,
                    "description": "该片段在视频叙事中的功能角色",
                },
            },
            "required": [
                "视觉表现",
                "语音类型",
                "summary",
                "画面小标题",
                "内容标签",
                "功能标签",
            ],
        },
    }

    return {"instruction": instruction, "schema": schema}


def _create_fallback(segment: Dict[str, Any]) -> Dict[str, Any]:
    """分析失败时的回退数据"""
    return {
        "index": segment["index"],
        "start": segment["start"],
        "end": segment["end"],
        "summary": "模型解析失败",
        "视觉表现": {"景别": "未知", "运镜": "未知", "画面内容": ""},
        "语音类型": "旁白",
        "is_speech": False,
        "speech_text": segment.get("speech_text"),
        "frame_urls": segment.get("frame_urls", []),
        "clip_url": segment.get("clip_url"),
        "画面小标题": "解析失败",
        "内容标签": [],
        "功能标签": "其他",
    }


def _strip_code_fence(text: str) -> str:
    """去除 markdown 代码块标记"""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


async def _analyze_single_segment(
    segment: Dict[str, Any],
    model_name: str,
    api_key: str,
    api_base: Optional[str] = None,
) -> Dict[str, Any]:
    """分析单个分镜（使用豆包官方 vision API）"""
    prompt_data = _build_segment_prompt(segment)
    messages = [
        {
            "role": "system",
            "content": "你是一名专业的视频拆解分析师，请严格输出JSON。",
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(prompt_data["instruction"], ensure_ascii=False),
                },
            ]
            + [
                {"type": "image_url", "image_url": {"url": url}}
                for url in segment.get("frame_urls", [])[:6]
            ],
        },
    ]

    max_retries = 3
    last_error = None

    for attempt in range(max_retries):
        try:
            # 调用豆包视觉 API（/responses endpoint，只传 model + input）
            response = await call_doubao_vision(
                model=model_name,
                messages=messages,
                api_key=api_key,
                api_base=api_base,
            )
            content = response["choices"][0]["message"]["content"]

            if isinstance(content, str):
                content = _strip_code_fence(content)
                structured = json.loads(content)
            else:
                structured = content

            # 填充基础信息
            structured["index"] = segment["index"]
            structured["start"] = segment["start"]
            structured["end"] = segment["end"]
            structured["frame_urls"] = segment.get("frame_urls", [])
            structured["clip_url"] = segment.get("clip_url")

            # 处理语音类型
            speech_type = structured.get("语音类型", "旁白")
            if speech_type in ["旁白口述", "非口播"]:
                speech_type = "旁白"
            structured["语音类型"] = speech_type
            structured["is_speech"] = speech_type == "口播"
            structured["speech_text"] = segment.get("speech_text")

            return structured

        except Exception as exc:
            last_error = exc
            logger.warning(
                f"分镜 {segment['index']} 分析失败 (尝试 {attempt + 1}/{max_retries}): {exc}"
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(1 + attempt)

    logger.error(f"分镜 {segment['index']} 分析最终失败: {last_error}")
    return _create_fallback(segment)


async def analyze_segments_vision(
    segments_json: str = "", tool_context: ToolContext = None
) -> str:
    """
    使用视觉模型分析每个分镜的画面内容、景别、运镜、功能标签。
    通过 LiteLLM 统一路由，支持 Gemini / 豆包 / GPT-4o 等多种模型。
    应在 process_video 之后调用。

    数据来源（按优先级）：
    1. 自动从 session state 中读取 process_video 的输出（推荐，无需手动传参）
    2. 显式传入 segments_json 参数

    Args:
        segments_json: （可选）JSON 字符串，格式为 process_video 返回的 segments 数组。
                       如果不传或为空，自动从 session state 读取 process_video_result。

    Returns:
        str: 分析结果的 JSON 字符串（数组），每个元素包含视觉分析、功能标签等完整信息。
    """
    # 优先从 session state 读取（无需 LLM 序列化 JSON）
    segments = None

    if tool_context and not segments_json:
        state_result = tool_context.state.get("process_video_result")
        if state_result and isinstance(state_result, dict):
            segments = state_result.get("segments", [])
            logger.info(
                f"[analyze_segments_vision] 从 session state 读取 {len(segments)} 个分镜"
            )

    # 回退：从参数解析
    if not segments and segments_json:
        try:
            parsed = (
                json.loads(segments_json)
                if isinstance(segments_json, str)
                else segments_json
            )
            if isinstance(parsed, dict):
                segments = parsed.get("segments", [])
            elif isinstance(parsed, list):
                segments = parsed
        except json.JSONDecodeError:
            return json.dumps(
                {"error": "segments_json 格式无效，需要合法 JSON 数组"},
                ensure_ascii=False,
            )

    if not segments or not isinstance(segments, list) or len(segments) == 0:
        return json.dumps(
            {"error": "没有可用的分镜数据。请先调用 process_video 处理视频。"},
            ensure_ascii=False,
        )

    # ---- 读取模型配置 ----
    # LiteLLM 模型名约定：
    #   gemini/gemini-2.5-pro      → 直连 Google (需 GEMINI_API_KEY)
    #   openai/gemini-2.5-pro      → OpenAI 兼容代理（如 OneRouter）
    #   doubao-seed-1-6-251015     → 火山方舟 (需 api_base + api_key)
    #   gpt-4o                     → OpenAI
    model_name = os.getenv("MODEL_VISION_NAME") or os.getenv(
        "MODEL_AGENT_NAME", "doubao-seed-1-6-vision"
    )
    api_key = (
        os.getenv("MODEL_VISION_API_KEY")
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("MODEL_AGENT_API_KEY")
        or os.getenv("OPENAI_API_KEY", "")
    )
    api_base = (
        os.getenv("MODEL_VISION_API_BASE")
        or os.getenv("MODEL_AGENT_API_BASE")
        or os.getenv("OPENAI_BASE_URL", "")
    )

    if not api_key:
        return json.dumps(
            {
                "error": "缺少 API Key，请配置 MODEL_VISION_API_KEY / GEMINI_API_KEY / MODEL_AGENT_API_KEY"
            },
            ensure_ascii=False,
        )

    # 过滤：只分析有帧图片的分镜
    segments_with_frames = [s for s in segments if s.get("frame_urls")]
    if not segments_with_frames:
        return json.dumps(
            {"error": "没有分镜包含帧图片URL，无法进行视觉分析"}, ensure_ascii=False
        )

    logger.info(
        f"[analyze_segments_vision] 开始分析 {len(segments_with_frames)} 个分镜 (model={model_name})"
    )

    # 并发分析，限制并发数
    concurrency = int(os.getenv("VISION_CONCURRENCY", "3"))
    semaphore = asyncio.Semaphore(concurrency)

    async def analyze_one(seg: Dict[str, Any]) -> Dict[str, Any]:
        async with semaphore:
            return await _analyze_single_segment(seg, model_name, api_key, api_base)

    tasks = [analyze_one(seg) for seg in segments_with_frames]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 处理结果
    valid_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"分镜 {segments_with_frames[i]['index']} 分析异常: {result}")
            valid_results.append(_create_fallback(segments_with_frames[i]))
        else:
            valid_results.append(result)

    valid_results.sort(key=lambda x: x["index"])

    logger.info(f"[analyze_segments_vision] 分析完成: {len(valid_results)} 个分镜")

    # 存入 session state（tool_context 可能为 None，如单元测试场景）
    if tool_context is not None:
        tool_context.state["vision_analysis_result"] = valid_results

    # 精简返回数据：移除 base64 frame_urls 以避免 LLM context 超限
    # 注意：完整数据已存入 session state，后续工具（如 hook_analyzer）可从 state 读取
    for result in valid_results:
        if "frame_urls" in result:
            frame_urls = result["frame_urls"]
            # 如果是 base64 data URL，替换为占位符以减少数据量
            result["frame_urls"] = [
                "（base64图片已省略）" if url and url.startswith("data:") else url
                for url in frame_urls
            ]
            logger.debug(
                f"分镜 {result['index']} 精简 frame_urls: {len(frame_urls)} 帧 → 占位符"
            )

    return json.dumps(valid_results, ensure_ascii=False)
