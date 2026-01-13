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

DEFAULT_MODEL_AGENT_NAME = "deepseek-v3-2-251201"
DEFAULT_MODEL_AGENT_API_BASE = "https://ark.cn-beijing.volces.com/api/v3/"

DEFAULT_VIDEO_MODEL_NAME = "doubao-seedance-1-0-pro-250528"
DEFAULT_VIDEO_MODEL_API_BASE = "https://ark.cn-beijing.volces.com/api/v3/"

DEFAULT_IMAGE_GENERATE_MODEL_NAME = "doubao-seedream-4-5-251128"
DEFAULT_IMAGE_GENERATE_MODEL_API_BASE = "https://ark.cn-beijing.volces.com/api/v3/"


def set_veadk_environment_variables():
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
