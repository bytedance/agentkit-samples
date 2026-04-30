#!/usr/bin/env python3
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

from __future__ import annotations

from enum import Enum


class AmkAuthMode(str, Enum):
    """AMK HTTP API 鉴权注册方式（与网关约定一致）。"""

    #: ``Authorization: Bearer <MediaKit API Key>``
    MEDIAKIT_ONLY = "mediakit_only"
    #: ``Authorization: Bearer <火山方舟 API Key>/<MediaKit API Key>``
    ARK_AND_MEDIAKIT = "ark_and_mediakit"
