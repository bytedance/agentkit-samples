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
import requests
from urllib.parse import urlencode

import logging
from model import *

# 请求接口信息
ADDR = os.getenv("ARK_SKILL_API_BASE")
TOKEN = os.getenv("ARK_SKILL_API_KEY") or ""
SERVICE = "iccloud_muse"
REGION = "cn-north"
ACTION = "SubmitAiTemplateTaskAsync"
VERSION = "2025-11-25"

# 请求示例
def _do_request(method: str, queries: dict, body: bytes, action: str, version: str = VERSION, service: str=SERVICE):
    """发起请求（支持GET/POST，包含签名逻辑）"""
    # 1. 处理查询参数，添加Action和Version
    queries["Action"] = action or ACTION
    queries["Version"] = version or VERSION

    # 构建请求地址
    query_string = urlencode(queries)
    query_string = query_string.replace("+", "%20")
    url = f"{ADDR}?{query_string}"

    # 4. 构建完整请求头
    headers = {
        "Content-Type": "application/json",
        "ServiceName": service,
        "Authorization": "Bearer " + TOKEN
    }

    # 6. 发起请求并处理响应
    logging.info(f">>> {method.upper()} {url} {headers} {body}")
    response = requests.request(method=method.upper(),url=url,headers=headers,data=body,timeout=30)
    logging.info(f"<<< {response.headers} {response.text}")

    return response

