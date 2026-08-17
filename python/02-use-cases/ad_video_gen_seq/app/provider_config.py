"""广告视频顺序编排案例的区域化模型默认值。"""

import os


def is_byteplus() -> bool:
    """判断当前运行环境是否使用 BytePlus。

    Function Purpose:
        为评估模型和媒体模型提供一致的云厂商判断。

    Implementation Logic:
        优先使用 CLOUD_PROVIDER；未显式配置时，根据 BYTEPLUS_REGION 推断。
    """
    provider = os.getenv("CLOUD_PROVIDER", "").strip().lower()
    return provider == "byteplus" or (
        not provider and bool(os.getenv("BYTEPLUS_REGION"))
    )


def get_model_api_base() -> str:
    """返回当前区域的模型 API Base URL。"""
    return (
        "https://ark.ap-southeast.bytepluses.com/api/v3"
        if is_byteplus()
        else "https://ark.cn-beijing.volces.com/api/v3"
    )


def get_evaluate_model() -> str:
    """返回当前区域支持的多模态评估模型。"""
    return (
        "dola-seed-2-1-turbo-260628"
        if is_byteplus()
        else "doubao-seed-1-6-251015"
    )
