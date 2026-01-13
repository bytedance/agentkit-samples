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

import os
import logging

from veadk.auth.veauth.ark_veauth import get_ark_token
from veadk.consts import DEFAULT_IMAGE_EDIT_MODEL_API_BASE

logger = logging.getLogger(__name__)


def get_ark_api_key() -> str:
    api_key = get_ark_token()
    if not api_key:
        api_key = os.getenv("MODEL_EDIT_API_KEY")
    if not api_key:
        logger.error(
            "Error: MODEL_EDIT_API_KEY is not provided or IAM Role is not configured."
        )
        return None
    return api_key


def get_base_url() -> str:
    base_url = os.getenv("MODEL_EDIT_API_BASE", DEFAULT_IMAGE_EDIT_MODEL_API_BASE)
    return base_url
