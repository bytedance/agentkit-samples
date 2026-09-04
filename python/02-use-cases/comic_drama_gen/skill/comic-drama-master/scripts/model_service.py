"""漫剧 Skill 脚本使用的区域化模型服务配置。"""

import os


_DEFAULTS = {
    "volcengine": {
        "api_base": "https://ark.cn-beijing.volces.com/api/v3",
        "image_model": "doubao-seedream-5-0-pro-260628",
        "video_model": "doubao-seedance-2-5-260628",
    },
    "byteplus": {
        "api_base": "https://ark.ap-southeast.bytepluses.com/api/v3",
        "image_model": "dola-seedream-5-0-pro-260628",
        "video_model": "dreamina-seedance-2-5-260628",
    },
}


def resolve_provider() -> str:
    """解析当前 Skill 应使用的云厂商。

    Function Purpose:
        让所有独立脚本共享相同的区域判断规则。

    Implementation Logic:
        显式 CLOUD_PROVIDER 优先；其次根据 BYTEPLUS_REGION 或非 cn 地域
        推断 BytePlus；缺少区域信息时兼容原有国内默认值。
    """
    provider = os.getenv("CLOUD_PROVIDER", "").strip().lower()
    if provider in _DEFAULTS:
        return provider
    if os.getenv("BYTEPLUS_REGION"):
        return "byteplus"
    region = os.getenv("VOLCENGINE_REGION", "").strip().lower()
    return "byteplus" if region and not region.startswith("cn-") else "volcengine"


def get_api_base() -> str:
    """返回显式配置或当前区域默认的模型 API Base URL。"""
    return (
        os.getenv("MODEL_AGENT_API_BASE") or _DEFAULTS[resolve_provider()]["api_base"]
    )


def get_image_api_base() -> str:
    """返回图片生成服务地址。"""
    return os.getenv("MODEL_IMAGE_API_BASE") or get_api_base()


def get_video_api_base() -> str:
    """返回视频生成服务地址。"""
    return os.getenv("MODEL_VIDEO_API_BASE") or get_api_base()


def get_image_model() -> str:
    """返回图片生成模型名称。"""
    return os.getenv("MODEL_IMAGE_NAME") or _DEFAULTS[resolve_provider()]["image_model"]


def get_video_model() -> str:
    """返回视频生成模型名称。"""
    return (
        os.getenv("DEFAULT_VIDEO_MODEL_NAME")
        or os.getenv("MODEL_VIDEO_NAME")
        or _DEFAULTS[resolve_provider()]["video_model"]
    )
