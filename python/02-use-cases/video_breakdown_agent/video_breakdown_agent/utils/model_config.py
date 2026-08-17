"""按云厂商解析视频拆解案例使用的模型服务默认值。"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelServiceDefaults:
    """单个云厂商的模型服务默认配置。"""

    api_base: str
    agent_model: str
    vision_model: str
    video_model: str
    video_text_model: str


_SERVICE_DEFAULTS = {
    "volcengine": ModelServiceDefaults(
        api_base="https://ark.cn-beijing.volces.com/api/v3",
        agent_model="doubao-seed-1-6-251015",
        vision_model="doubao-seed-1-6-vision-250815",
        video_model="doubao-seedance-2-0-260128",
        video_text_model="doubao-seedance-1-0-pro-250528",
    ),
    "byteplus": ModelServiceDefaults(
        api_base="https://ark.ap-southeast.bytepluses.com/api/v3",
        agent_model="dola-seed-2-1-turbo-260628",
        vision_model="dola-seed-2-1-turbo-260628",
        video_model="dreamina-seedance-2-0-260128",
        video_text_model="dreamina-seedance-2-0-260128",
    ),
}


def resolve_cloud_provider() -> str:
    """解析模型服务所属云厂商。

    Function Purpose:
        为全部子 Agent 提供唯一的区域判断入口。

    Implementation Logic:
        优先读取 CLOUD_PROVIDER；缺失时根据 BYTEPLUS_REGION 或非 cn 地域
        推断 BytePlus，无法判断时保持 volcengine 默认值以兼容国内案例。
    """
    provider = os.getenv("CLOUD_PROVIDER", "").strip().lower()
    if provider in _SERVICE_DEFAULTS:
        return provider
    if os.getenv("BYTEPLUS_REGION"):
        return "byteplus"
    region = os.getenv("VOLCENGINE_REGION", "").strip().lower()
    return "byteplus" if region and not region.startswith("cn-") else "volcengine"


def get_model_service_defaults() -> ModelServiceDefaults:
    """返回当前区域对应的模型服务默认配置。"""
    return _SERVICE_DEFAULTS[resolve_cloud_provider()]


def configure_model_environment() -> None:
    """为视频拆解案例填充区域化模型环境变量。

    Function Purpose:
        保证 VeADK Agent、自定义 HTTP 客户端和视频工具使用同一服务面。

    Implementation Logic:
        根据云厂商选择配置，并通过 setdefault 仅补齐缺失项，保留用户通过
        环境变量显式指定模型、API 地址或第三方兼容服务的能力。
    """
    defaults = get_model_service_defaults()
    os.environ.setdefault("MODEL_AGENT_NAME", defaults.agent_model)
    os.environ.setdefault("MODEL_AGENT_API_BASE", defaults.api_base)
    os.environ.setdefault("MODEL_VISION_NAME", defaults.vision_model)
    os.environ.setdefault("MODEL_VISION_API_BASE", defaults.api_base)
    os.environ.setdefault("MODEL_FORMAT_NAME", defaults.agent_model)
    os.environ.setdefault("MODEL_BGM_NAME", defaults.agent_model)
    os.environ.setdefault("MODEL_BGM_API_BASE", defaults.api_base)
    os.environ.setdefault("MODEL_VIDEO_NAME", defaults.video_model)
    os.environ.setdefault("MODEL_VIDEO_API_BASE", defaults.api_base)
