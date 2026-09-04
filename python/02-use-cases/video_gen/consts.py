# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging
import os

logger = logging.getLogger(__name__)

DEFAULT_BUCKET = "video_generation_output"
DEFAULT_REGION = "cn-beijing"

_MODEL_SERVICE_DEFAULTS = {
    "volcengine": {
        "agent_name": "deepseek-v4-pro-260425",
        "api_base": "https://ark.cn-beijing.volces.com/api/v3/",
        "video_name": "doubao-seedance-2-5-260628",
        "image_name": "doubao-seedream-5-0-pro-260628",
    },
    "byteplus": {
        "agent_name": "deepseek-v4-pro-260425",
        "api_base": "https://ark.ap-southeast.bytepluses.com/api/v3/",
        "video_name": "dreamina-seedance-2-5-260628",
        "image_name": "dola-seedream-5-0-pro-260628",
    },
}


def _resolve_cloud_provider() -> str:
    """解析当前模型服务所属云厂商。

    Function Purpose:
        为模型名称和 API 地址选择提供统一、确定性的区域依据。

    Implementation Logic:
        优先采用显式 CLOUD_PROVIDER；未配置时根据 BYTEPLUS_REGION 和
        VOLCENGINE_REGION 推断，最终保持国内 volcengine 默认行为。
    """
    provider = os.getenv("CLOUD_PROVIDER", "").strip().lower()
    if provider in _MODEL_SERVICE_DEFAULTS:
        return provider
    if os.getenv("BYTEPLUS_REGION"):
        return "byteplus"
    region = os.getenv("VOLCENGINE_REGION", "").strip().lower()
    return "byteplus" if region and not region.startswith("cn-") else "volcengine"


def set_veadk_environment_variables():
    """按云厂商注入 VeADK 模型环境变量默认值。

    Function Purpose:
        确保国内方舟与 BytePlus ModelArk 使用各自可用的模型和服务地址。

    Implementation Logic:
        根据区域配置选择默认配置集合，仅填充用户未显式设置的环境变量，
        从而保留自定义模型、接入点和代理地址的优先级。
    """
    defaults = _MODEL_SERVICE_DEFAULTS[_resolve_cloud_provider()]

    os.environ["MODEL_AGENT_NAME"] = os.getenv(
        "MODEL_AGENT_NAME", defaults["agent_name"]
    )
    os.environ["MODEL_AGENT_API_BASE"] = os.getenv(
        "MODEL_AGENT_API_BASE", defaults["api_base"]
    )

    os.environ["MODEL_VIDEO_NAME"] = os.getenv(
        "MODEL_VIDEO_NAME", defaults["video_name"]
    )
    os.environ["MODEL_VIDEO_API_BASE"] = os.getenv(
        "MODEL_VIDEO_API_BASE", defaults["api_base"]
    )

    os.environ["MODEL_IMAGE_NAME"] = os.getenv(
        "MODEL_IMAGE_NAME", defaults["image_name"]
    )
    os.environ["MODEL_IMAGE_API_BASE"] = os.getenv(
        "MODEL_IMAGE_API_BASE", defaults["api_base"]
    )
