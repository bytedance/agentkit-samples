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
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_REGION = "cn-beijing"

_MODEL_SERVICE_DEFAULTS = {
    "volcengine": {
        "agent_name": "deepseek-v4-pro-260425",
        "api_base": "https://ark.cn-beijing.volces.com/api/v3/",
        "video_name": "doubao-seedance-2-0-260128",
        "image_name": "doubao-seedream-5-0-pro-260628",
    },
    "byteplus": {
        "agent_name": "deepseek-v4-pro-260425",
        "api_base": "https://ark.ap-southeast.bytepluses.com/api/v3/",
        "video_name": "dreamina-seedance-2-0-260128",
        "image_name": "dola-seedream-5-0-pro-260628",
    },
}


def _resolve_cloud_provider() -> str:
    """解析当前模型服务所属云厂商。

    Function Purpose:
        为主 Agent 和 Skill 子进程选择一致的模型服务面。

    Implementation Logic:
        优先读取 CLOUD_PROVIDER，其次根据 BYTEPLUS_REGION 或地域前缀推断，
        无区域信息时保持 volcengine 默认值。
    """
    provider = os.getenv("CLOUD_PROVIDER", "").strip().lower()
    if provider in _MODEL_SERVICE_DEFAULTS:
        return provider
    if os.getenv("BYTEPLUS_REGION"):
        return "byteplus"
    region = os.getenv("VOLCENGINE_REGION", "").strip().lower()
    return "byteplus" if region and not region.startswith("cn-") else "volcengine"


def _load_dotenv():
    """加载当前目录的 .env 文件（优先使用 python-dotenv，若未安装则手动解析）。"""
    env_file = Path(__file__).resolve().parent / ".env"
    if not env_file.exists():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(dotenv_path=env_file, override=False)
        logger.info(f"[consts] Loaded .env via python-dotenv: {env_file}")
    except ImportError:
        # python-dotenv 未安装，手动解析
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip().lstrip("export ").strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
        logger.info(f"[consts] Loaded .env manually: {env_file}")


def set_veadk_environment_variables():
    """加载本地配置并填充区域化模型默认值。"""
    _load_dotenv()
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
