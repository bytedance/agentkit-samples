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
"""统一的 Job API 响应解析工具。"""

from typing import Any, Dict, Tuple

ApiResponseTuple = Tuple[bool, str, str, Any, Dict[str, Any]]


def parse_api_response(response: Dict[str, Any]) -> ApiResponseTuple:
    """解析接口响应并返回统一结构。

    判定规则：
    - 若 ``ResponseMetadata.Error`` 不存在，视为成功；
    - 若 ``ResponseMetadata.Error.Code`` 为 "0" 或 0，视为成功；
    - 否则视为异常。

    返回值为 (is_ok, error_code, error_message, result, response_metadata)。
    """
    if not isinstance(response, dict):
        return (
            False,
            "InvalidResponse",
            "Response is not a JSON object.",
            None,
            {},
        )

    metadata_raw = response.get("ResponseMetadata")
    result = response.get("Result")

    if not isinstance(metadata_raw, dict):
        # 缺失或错误的 ResponseMetadata 视为异常
        return (
            False,
            "MissingResponseMetadata",
            "ResponseMetadata is missing or invalid.",
            result,
            metadata_raw if isinstance(metadata_raw, dict) else {},
        )

    error = metadata_raw.get("Error")
    if not error or not isinstance(error, dict):
        # 没有 Error 字段，视为成功
        return True, "0", "", result, metadata_raw

    code = error.get("Code")
    message = error.get("Message", "")

    # Code 为 "0" 或 0 时视为成功
    if code in (None, "", "0", 0):
        return True, "0", "", result, metadata_raw

    return False, str(code), str(message), result, metadata_raw


def is_response_ok(response: Dict[str, Any]) -> bool:
    """便捷方法：仅判断响应是否成功。"""
    is_ok, _, _, _, _ = parse_api_response(response)
    return is_ok
