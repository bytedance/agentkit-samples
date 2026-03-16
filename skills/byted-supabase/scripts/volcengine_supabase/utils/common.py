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
import json
from typing import Any


def to_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)


def compact_dict(payload: dict) -> dict:
    return {key: value for key, value in payload.items() if value is not None}


def pick_value(source: Any, *field_names: str) -> Any:
    source_dict = source.to_dict() if hasattr(source, "to_dict") else source if isinstance(source, dict) else {}
    for field_name in field_names:
        value = None
        if isinstance(source, dict):
            value = source.get(field_name)
        else:
            value = getattr(source, field_name, None)
        if value is None and isinstance(source_dict, dict):
            value = source_dict.get(field_name)
        if isinstance(value, str):
            value = value.strip()
            if not value:
                value = None
        if value is not None:
            return value
    return None
