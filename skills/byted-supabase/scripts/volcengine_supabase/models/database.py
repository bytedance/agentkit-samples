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
from typing import Optional, List
from pydantic import BaseModel, Field


class Column(BaseModel):
    name: str
    format: str
    is_nullable: Optional[bool] = None
    is_unique: Optional[bool] = None
    default_value: Optional[str] = None


class Table(BaseModel):
    schema_name: str = Field(alias="schema")
    name: str
    columns: List[Column] = []
    
    class Config:
        populate_by_name = True


class Migration(BaseModel):
    version: str
    name: str
