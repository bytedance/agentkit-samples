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
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class EdgeFunction(BaseModel):
    id: str
    slug: str
    name: str
    status: str
    version: int
    created_at: str
    updated_at: str
    verify_jwt: bool
    entrypoint_path: str
    runtime_config: Optional[str] = None
    runtime: Optional[str] = None


class EdgeFunctionFile(BaseModel):
    name: str
    content: str


class EdgeFunctionDeployment(BaseModel):
    name: str
    entrypoint_path: str = "index.ts"
    verify_jwt: bool = True
    import_map_path: Optional[str] = None
    files: List[EdgeFunctionFile]
