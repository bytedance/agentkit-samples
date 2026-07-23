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

DEFAULT_MODEL_AGENT_NAME = "deepseek-v3-2-251201"
DEFAULT_MODEL_AGENT_API_BASE = "https://ark.cn-beijing.volces.com/api/v3/"

DEFAULT_VIDEO_MODEL_NAME = "doubao-seedance-1-5-pro-251215"
DEFAULT_VIDEO_MODEL_API_BASE = "https://ark.cn-beijing.volces.com/api/v3/"

DEFAULT_IMAGE_GENERATE_MODEL_NAME = "doubao-seedream-5-0-260128"
DEFAULT_IMAGE_GENERATE_MODEL_API_BASE = "https://ark.cn-beijing.volces.com/api/v3/"


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
    # 优先从 .env 文件加载环境变量（不覆盖已存在的变量）
    _load_dotenv()

    os.environ["MODEL_AGENT_NAME"] = os.getenv(
        "MODEL_AGENT_NAME", DEFAULT_MODEL_AGENT_NAME
    )
    os.environ["MODEL_AGENT_API_BASE"] = os.getenv(
        "MODEL_AGENT_API_BASE", DEFAULT_MODEL_AGENT_API_BASE
    )

    os.environ["MODEL_VIDEO_NAME"] = os.getenv(
        "MODEL_VIDEO_NAME", DEFAULT_VIDEO_MODEL_NAME
    )
    os.environ["MODEL_VIDEO_API_BASE"] = os.getenv(
        "MODEL_VIDEO_API_BASE", DEFAULT_VIDEO_MODEL_API_BASE
    )

    os.environ["MODEL_IMAGE_NAME"] = os.getenv(
        "MODEL_IMAGE_NAME", DEFAULT_IMAGE_GENERATE_MODEL_NAME
    )
    os.environ["MODEL_IMAGE_API_BASE"] = os.getenv(
        "MODEL_IMAGE_API_BASE", DEFAULT_IMAGE_GENERATE_MODEL_API_BASE
    )
