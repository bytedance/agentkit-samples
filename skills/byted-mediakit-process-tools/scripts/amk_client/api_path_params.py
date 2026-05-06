"""各 API 路径占位符对应的 Pydantic 校验模型（与 ``api_config`` 中 ``action`` 的 ``{name}`` 一致）。"""

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

from pydantic import BaseModel, ConfigDict, Field


class QueryTaskPathParams(BaseModel):
    """``GET /api/v1/tasks/{task_id}``"""

    model_config = ConfigDict(str_strip_whitespace=True)

    task_id: str = Field(..., min_length=1, description="任务 ID")
