"""
数据类型定义
定义 Pydantic 模型用于 Agent 输出格式校验
"""

from typing import List, Optional

from google.genai import types
from pydantic import BaseModel, Field

# JSON 输出配置
json_response_config = types.GenerateContentConfig(
    response_mime_type="application/json",
    max_output_tokens=18000,
)


class HookAnalysis(BaseModel):
    """前三秒钩子分析结果的结构化输出"""

    overall_score: float = Field(description="综合评分(0-10)，各维度加权平均")
    visual_impact: float = Field(description="视觉冲击力分数(0-10)")
    visual_comment: str = Field(description="视觉冲击力的具体评价")
    language_hook: float = Field(description="语言钩子分数(0-10)")
    language_comment: str = Field(description="语言钩子的具体评价")
    emotion_trigger: float = Field(description="情绪唤起分数(0-10)")
    emotion_comment: str = Field(description="情绪唤起的具体评价")
    information_density: float = Field(description="信息密度分数(0-10)")
    info_comment: str = Field(description="信息密度的具体评价")
    rhythm_control: float = Field(description="节奏掌控分数(0-10)")
    rhythm_comment: str = Field(description="节奏掌控的具体评价")
    hook_type: str = Field(
        description="钩子类型（痛点型/好奇型/冲突型/价值型/情感型/视觉冲击型/悬念型）"
    )
    hook_type_analysis: Optional[str] = Field(
        default="", description="为什么判定为该钩子类型的详细理由"
    )
    target_audience: Optional[str] = Field(default="", description="推测的目标受众画像")
    strengths: List[str] = Field(description="优点列表（需具体引用画面元素）")
    weaknesses: List[str] = Field(description="不足列表（需具体指出问题）")
    suggestions: List[str] = Field(
        description="优化建议列表（说明改什么、怎么改、预期效果）"
    )
    competitor_reference: Optional[str] = Field(
        default="", description="同品类/同类型优秀视频的钩子设计参考"
    )
    retention_prediction: str = Field(
        description="3秒留存预测（高/中/低）及详细原因分析"
    )
