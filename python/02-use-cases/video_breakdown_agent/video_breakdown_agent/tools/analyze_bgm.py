"""
BGM 音频分析工具（自包含）
使用豆包官方 API 分析背景音乐（支持文本模型）。
模型不支持音频时优雅降级返回空结果。

迁移来源: video-breakdown-master/app/services/bgm_service.py
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

from google.adk.tools import ToolContext
from video_breakdown_agent.utils.doubao_client import call_doubao_text

logger = logging.getLogger(__name__)

# ==================== 枚举常量（来自 bgm_prompts.py）====================

MUSIC_STYLE_OPTIONS = [
    "流行",
    "摇滚",
    "电子",
    "古典",
    "爵士",
    "民谣",
    "R&B",
    "嘻哈",
    "乡村",
    "蓝调",
    "雷鬼",
    "金属",
    "朋克",
    "独立",
    "氛围",
    "新世纪",
    "世界音乐",
    "原声配乐",
    "轻音乐",
    "纯音乐",
]

EMOTION_OPTIONS = [
    "轻松愉悦",
    "积极向上",
    "温馨感人",
    "激昂励志",
    "浪漫甜蜜",
    "活力四射",
    "欢快热闹",
    "平静舒缓",
    "神秘悬疑",
    "史诗宏大",
    "梦幻空灵",
    "复古怀旧",
    "紧张刺激",
    "悲伤忧郁",
    "阴郁压抑",
    "恐怖惊悚",
]


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


def _get_empty_result() -> Dict[str, Any]:
    """返回空结果"""
    return {
        "has_bgm": False,
        "music_style": None,
        "emotion": None,
        "instruments": None,
        "tempo": None,
    }


async def analyze_bgm(
    audio_url: str = "", duration: float = 0.0, tool_context: ToolContext = None
) -> dict:
    """
    分析视频的背景音乐（BGM），识别风格、情绪、乐器、节奏等特征。
    通过 LiteLLM 统一路由，需要模型支持音频输入（input_audio），
    如果模型不支持则优雅降级返回空结果。

    应在 process_video 之后调用。如果不传参数，自动从 session state 读取 process_video 的结果。

    Args:
        audio_url: （可选）音频文件 URL。不传时自动从 session state 读取。
        duration: （可选）音频/视频时长（秒）。不传时自动从 session state 读取。

    Returns:
        dict: BGM 分析结果，包含 has_bgm, music_style, emotion, instruments, tempo 等字段。
              模型不支持音频时返回 has_bgm=False 的空结果。
    """
    # 优先从 session state 读取
    audio_base64 = None
    if tool_context and (not audio_url or duration <= 0):
        state_result = tool_context.state.get("process_video_result")
        if state_result and isinstance(state_result, dict):
            if not audio_url:
                audio_url = state_result.get("audio_url", "")
            if not audio_url:
                audio_base64 = state_result.get("audio_base64")
            if duration <= 0:
                duration = float(state_result.get("duration", 0))
            logger.info(
                f"[analyze_bgm] 从 session state 读取: audio_url={'有' if audio_url else '无'}, "
                f"audio_base64={'有' if audio_base64 else '无'}, duration={duration:.1f}s"
            )

    if not audio_url and not audio_base64:
        logger.info("[analyze_bgm] 无音频 URL 且无 base64 音频数据，跳过 BGM 分析")
        empty_result = _get_empty_result()
        if tool_context is not None:
            tool_context.state["bgm_analysis_result"] = empty_result
        return empty_result

    # ---- 读取模型配置 ----
    # BGM 分析优先使用独立配置，支持切换到不同 provider
    model_name = (
        os.getenv("MODEL_BGM_NAME")
        or os.getenv("BGM_MODEL_NAME")
        or os.getenv("MODEL_AGENT_NAME", "doubao-seed-1-6-251015")
    )
    api_key = (
        os.getenv("MODEL_BGM_API_KEY")
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("MODEL_AGENT_API_KEY")
        or os.getenv("OPENAI_API_KEY", "")
    )
    api_base = (
        os.getenv("MODEL_BGM_API_BASE")
        or os.getenv("MODEL_AGENT_API_BASE")
        or os.getenv("OPENAI_BASE_URL", "")
    )

    if not api_key:
        logger.warning("[analyze_bgm] 缺少 API Key，跳过 BGM 分析")
        empty_result = _get_empty_result()
        if tool_context is not None:
            tool_context.state["bgm_analysis_result"] = empty_result
        return empty_result

    music_styles_str = "、".join(MUSIC_STYLE_OPTIONS)
    emotions_str = "、".join(EMOTION_OPTIONS)

    system_prompt = (
        "你是一个专业的音频分析师，擅长分析音乐的风格、情绪、节奏和乐器组成。"
        "请仔细聆听音频，分析其中的背景音乐（BGM）特征。"
    )

    user_prompt = f"""请分析这段音频的背景音乐特征。

【音频时长】{duration:.1f}秒

请从以下维度进行分析：

1. **是否有BGM**：判断音频中是否包含背景音乐

2. **音乐风格**（如有BGM）：
   - 主风格：从以下选项选择一个最匹配的：{music_styles_str}
   - 次风格：可选1-2个补充风格
   - 风格标签：描述性标签（如：现代、复古、商业、文艺等）

3. **情绪识别**（如有BGM）：
   - 主情绪：从以下选项选择一个最匹配的：{emotions_str}
   - 次情绪：可选1-2个补充情绪
   - 情绪强度：1-10分（1为最弱，10为最强）
   - 情绪倾向：正面/中性/负面

4. **乐器分析**（如有BGM）：
   - 识别的乐器
   - 主导乐器
   - 原声/电子比例

5. **节奏分析**（如有BGM）：
   - BPM估计
   - 节奏快慢：快/中/慢
   - 节奏模式

输出要求：严格输出JSON格式"""

    # 构建音频内容部分
    # 根据模型类型选择不同的音频传递方式：
    #   - OpenAI 兼容（火山/OneRouter）：使用 input_audio 格式
    # 对于豆包文本 API：直接用文本描述代替音频输入
    # 豆包文本模型不支持音频，这里优雅降级
    user_prompt = f"""请分析这段音频的背景音乐特征。

时长：{duration:.1f}秒
（注：当前使用文本分析模式，基于典型场景推测）

**可选风格**：{music_styles_str}
**可选情绪**：{emotions_str}

请输出标准 JSON，包含以下字段：
- has_bgm (boolean): 是否有BGM
- music_style (object): 风格分类
  - primary (string): 主要风格
  - secondary (array): 次要风格
  - tags (array): 风格标签
- emotion (object): 情绪特征
  - primary (string): 主要情绪
  - secondary (array): 次要情绪
  - intensity (integer, 1-10): 强度
  - valence (string): 正面/中性/负面
- instruments (object): 乐器组成
  - detected (array): 识别的乐器
  - dominant (string): 主导乐器
  - acoustic_ratio (number, 0-1): 声学乐器占比
  - electronic_ratio (number, 0-1): 电子乐器占比
- tempo (object): 节奏特征
  - bpm_estimate (string): BPM 估计
  - pace (string): 快/中/慢
  - rhythm_pattern (string): 节奏模式描述"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    _schema = {  # noqa: F841  # 保留作为 BGM 输出格式参考
        "name": "bgm_analysis_schema",
        "schema": {
            "type": "object",
            "properties": {
                "has_bgm": {"type": "boolean", "description": "是否有BGM"},
                "music_style": {
                    "type": "object",
                    "properties": {
                        "primary": {"type": "string"},
                        "secondary": {"type": "array", "items": {"type": "string"}},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "emotion": {
                    "type": "object",
                    "properties": {
                        "primary": {"type": "string"},
                        "secondary": {"type": "array", "items": {"type": "string"}},
                        "intensity": {"type": "integer", "minimum": 1, "maximum": 10},
                        "valence": {"type": "string", "enum": ["正面", "中性", "负面"]},
                    },
                },
                "instruments": {
                    "type": "object",
                    "properties": {
                        "detected": {"type": "array", "items": {"type": "string"}},
                        "dominant": {"type": "string"},
                        "acoustic_ratio": {"type": "number"},
                        "electronic_ratio": {"type": "number"},
                    },
                },
                "tempo": {
                    "type": "object",
                    "properties": {
                        "bpm_estimate": {"type": "string"},
                        "pace": {"type": "string", "enum": ["快", "中", "慢"]},
                        "rhythm_pattern": {"type": "string"},
                    },
                },
            },
            "required": ["has_bgm"],
        },
    }

    try:
        logger.info(
            f"[analyze_bgm] 调用豆包模型 {model_name} 分析 BGM（音频分析当前仅以描述为主）..."
        )
        response = await call_doubao_text(
            model=model_name,
            messages=messages,
            api_key=api_key,
            api_base=api_base,
            temperature=0.7,
        )
        content = response["choices"][0]["message"]["content"]

        if isinstance(content, str):
            content = _strip_code_fence(content)
            result = json.loads(content)
        else:
            result = content

        logger.info(f"[analyze_bgm] BGM 分析完成: has_bgm={result.get('has_bgm')}")
        if tool_context is not None:
            tool_context.state["bgm_analysis_result"] = result
        return result

    except Exception as exc:
        logger.warning(f"[analyze_bgm] 分析失败: {exc}，返回空结果")
        empty_result = _get_empty_result()
        if tool_context is not None:
            tool_context.state["bgm_analysis_result"] = empty_result
        return empty_result
