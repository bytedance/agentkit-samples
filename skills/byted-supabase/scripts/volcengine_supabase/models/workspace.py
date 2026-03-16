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
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Workspace(BaseModel):
    workspace_id: str
    workspace_name: str
    status: str
    region: str
    create_time: str
    engine_type: str
    engine_version: str


class Branch(BaseModel):
    branch_id: str
    branch_name: Optional[str] = None
    default: bool = False
    workspace_id: Optional[str] = None


class ApiKey(BaseModel):
    key: str
    name: str
    type: str
    create_time: Optional[str] = None
