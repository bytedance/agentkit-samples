"""
数据模型定义 - 视频复刻Agent
参考: multimedia/director-agent/src/director_agent/utils/types.py
"""

from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from google.genai import types

# JSON输出配置
json_response_config = types.GenerateContentConfig(
    response_mime_type="application/json",
    max_output_tokens=18000,
)

max_output_tokens_config = types.GenerateContentConfig(
    max_output_tokens=18000,
)


class VideoPrompt(BaseModel):
    """单个分镜的视频生成提示词"""

    segment_index: int = Field(description="分镜索引（从1开始）")
    segment_name: str = Field(description="分镜名称，格式：segment_1")
    start_time: float = Field(description="开始时间（秒）")
    end_time: float = Field(description="结束时间（秒）")
    duration: float = Field(description="时长（秒）")

    # 提示词内容
    positive_prompt: str = Field(description="正向提示词（基于电影级标准范式）")
    negative_prompt: str = Field(
        default="模糊，扭曲，低质量，失焦，噪点，水印", description="负向提示词"
    )

    # 参考图片
    first_frame: Optional[str] = Field(
        default=None, description="参考首帧图片URL或base64"
    )
    last_frame: Optional[str] = Field(
        default=None, description="参考尾帧图片URL或base64"
    )

    # 生成参数
    resolution: str = Field(default="720p", description="分辨率（720p/1080p）")
    ratio: str = Field(default="9:16", description="宽高比（16:9/9:16/1:1）")
    fps: int = Field(default=24, description="帧率")

    # 选择状态
    selected: bool = Field(default=False, description="是否选中生成")
    estimated_cost: float = Field(default=5.0, description="预估费用（元）")

    # 原始分镜数据（用于评估对比）
    original_segment_data: Optional[Dict] = Field(
        default=None, description="原始分镜数据"
    )


class VideoPromptList(BaseModel):
    """视频生成提示词列表"""

    prompts: List[VideoPrompt] = Field(description="提示词列表")
    total_count: int = Field(default=0, description="总分镜数")
    total_selected: int = Field(default=0, description="已选中数量")
    total_duration: float = Field(default=0.0, description="总时长（秒）")
    total_cost: float = Field(default=0.0, description="总预估费用（元）")

    # 风格配置
    style_config: Optional[Dict] = Field(default=None, description="整体风格配置")
    style_transfer_enabled: bool = Field(default=False, description="是否启用风格迁移")
    transfer_target: Optional[str] = Field(
        default=None, description="迁移目标（如：手机壳产品）"
    )


class VideoGenerationResult(BaseModel):
    """视频生成结果"""

    status: str = Field(description="状态：success/error/partial")
    message: Optional[str] = Field(default=None, description="状态消息")

    # 生成结果
    generated_videos: List[Dict] = Field(
        default_factory=list,
        description="已生成视频列表，格式：[{'segment_1': 'video_url'}]",
    )
    error_list: List[str] = Field(default_factory=list, description="失败分镜列表")

    # 拼接结果
    merged_video_url: Optional[str] = Field(
        default=None, description="拼接后的完整视频URL"
    )
    merged_video_path: Optional[str] = Field(
        default=None, description="拼接后的本地路径"
    )

    # 统计信息
    total_requested: int = Field(default=0, description="请求生成数量")
    total_succeeded: int = Field(default=0, description="成功生成数量")
    total_failed: int = Field(default=0, description="失败数量")
    actual_cost: float = Field(default=0.0, description="实际费用（元）")


class VideoEvaluationResult(BaseModel):
    """视频评估结果"""

    # 基础信息
    original_video_url: str = Field(description="原片URL")
    recreated_video_url: str = Field(description="复刻视频URL")

    # 对比数据
    original_hook_score: float = Field(default=0.0, description="原片钩子评分")
    recreated_hook_score: float = Field(default=0.0, description="复刻钩子评分")
    similarity: float = Field(default=0.0, description="相似度（0-100）")

    # 详细对比
    comparison_details: Dict = Field(
        default_factory=dict, description="详细对比数据（视觉、节奏、氛围等）"
    )

    # 综合评估
    overall_score: int = Field(default=0, description="综合质量得分（0-100）")
    strengths: List[str] = Field(default_factory=list, description="优点列表")
    improvements: List[str] = Field(default_factory=list, description="改进建议")

    # 元数据
    evaluation_time: Optional[str] = Field(default=None, description="评估时间")


class StyleTransferConfig(BaseModel):
    """风格迁移配置"""

    transfer_mode: str = Field(
        default="theme",
        description="迁移模式：theme（主题替换）/scene（场景迁移）/hybrid（混合）",
    )

    # 替换目标
    original_product: Optional[str] = Field(default=None, description="原产品描述")
    target_product: str = Field(description="目标产品描述")

    # 保留元素
    preserve_camera: bool = Field(default=True, description="保留镜头语言")
    preserve_lighting: bool = Field(default=True, description="保留光影风格")
    preserve_pacing: bool = Field(default=True, description="保留节奏")

    # 替换元素
    replace_background: bool = Field(default=False, description="替换背景")
    new_background: Optional[str] = Field(default=None, description="新背景描述")

    # LLM辅助
    use_llm_enhancement: bool = Field(default=True, description="使用LLM智能优化")
