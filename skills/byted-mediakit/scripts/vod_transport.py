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
"""
VOD 请求传输层：apig（SkillHub Bearer）优先，否则 cloud（火山 HMAC OpenAPI）。
"""
from __future__ import annotations
import json
import os
from typing import Literal, Union
import requests
from urllib.parse import quote, urlencode
from volc_request import VolcRequestClient
from log_utils import bail, log

def _strip_env(name: str) -> str:
    raw = os.getenv(name)
    return (raw or "").strip()


def _normalize_skillhub_api_base(base: str) -> str:
    """ARK_SKILL_API_BASE 可能只配主机名；requests 需要带 scheme 的绝对 URL。"""
    base = base.strip().rstrip("/")
    if not base:
        return base
    if "://" in base:
        return base
    return f"https://{base}"


def resolve_vod_transport() -> Literal["apig", "cloud"]:
    if _strip_env("ARK_SKILL_API_BASE") and _strip_env("ARK_SKILL_API_KEY"):
        return "apig"
    return "cloud"


class SkillhubApigVodClient:
    """
    SkillHub API 网关：请求形态与火山 VOD OpenAPI 一致（Action/Version + query / JSON body），
    鉴权为 Bearer + ServiceName: vod，不做 HMAC 签算。
    """

    def __init__(self, api_base: str, api_key: str):
        self.api_base = _normalize_skillhub_api_base(api_base)
        self.api_key = api_key.strip()

    def get(self, action: str, version: str, params: dict | None = None) -> str:
        return self._request(action, params or {}, "GET", version)

    def post(self, action: str, version: str, body: dict) -> str:
        return self._request(action, body or {}, "POST", version)

    def _request(self, action: str, data: dict, method: str, version: str) -> str:
        query_params = {"Action": action, "Version": version}
        body_dict: dict = {}
        if method == "GET":
            if data:
                query_params.update(data)
        else:
            body_dict = data or {}

        canonical_query = urlencode(sorted(query_params.items()), quote_via=quote, safe="-_.~")
        url = f"{self.api_base}?{canonical_query}"

        json_body = "" if method == "GET" else json.dumps(body_dict, ensure_ascii=False)
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {self.api_key}",
            "ServiceName": "vod",
        }
        if method == "GET":
            r = requests.get(url, headers=headers)
        else:
            r = requests.post(url, headers=headers, data=json_body.encode("utf-8"))

        if r.status_code != 200:
            raise Exception(f"HTTP {r.status_code}: {r.text}")
        return r.text


def load_credentials():
    if "VOLCENGINE_ACCESS_KEY_ID" in os.environ:
        ak = os.environ.get("VOLCENGINE_ACCESS_KEY_ID")
    elif "VOLC_ACCESSKEY" in os.environ:
        ak = os.environ.get("VOLC_ACCESSKEY")
    elif "VOLC_ACCESS_KEY" in os.environ:
        ak = os.environ.get("VOLC_ACCESS_KEY")
    elif "VOLCENGINE_ACCESS_KEY" in os.environ:
        ak = os.environ.get("VOLCENGINE_ACCESS_KEY")
    elif "VOLC_ACCESS_KEY_ID" in os.environ:
        ak = os.environ.get("VOLC_ACCESS_KEY_ID")
    else:
        ak = None

    if "VOLCENGINE_ACCESS_KEY_SECRET" in os.environ:
        sk = os.environ.get("VOLCENGINE_ACCESS_KEY_SECRET")
    elif "VOLC_SECRETKEY" in os.environ:
        sk = os.environ.get("VOLC_SECRETKEY")
    elif "VOLC_SECRET_KEY" in os.environ:
        sk = os.environ.get("VOLC_SECRET_KEY")
    elif "VOLCENGINE_SECRET_KEY" in os.environ:
        sk = os.environ.get("VOLCENGINE_SECRET_KEY")
    elif "VOLC_ACCESS_KEY_SECRET" in os.environ:
        sk = os.environ.get("VOLC_ACCESS_KEY_SECRET")
    else:
        sk = None

    if ak and sk:
        return ak, sk
    bail("未找到 AK/SK。请设置环境变量 VOLCENGINE_ACCESS_KEY_ID / VOLCENGINE_ACCESS_KEY_SECRET，或放置 .env 文件。")

def get_vod_transport_client() -> Union[SkillhubApigVodClient, VolcRequestClient]:
    if resolve_vod_transport() == "apig":
        log("使用 SkillHub 网关")
        base = _strip_env("ARK_SKILL_API_BASE")
        key = _strip_env("ARK_SKILL_API_KEY")
        return SkillhubApigVodClient(base, key)

    ak, sk = load_credentials()
    log("使用火山引擎 OpenAPI")
    return VolcRequestClient(
        ak=ak,
        sk=sk,
        host="vod.volcengineapi.com",
        region="cn-north-1",
        service="vod",
    )
