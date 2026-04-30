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
import hashlib
import hmac
import json
from datetime import datetime, timezone
from functools import reduce


import requests
from urllib.parse import urlencode, quote


class VolcRequestClient:
    """
    火山引擎 API 请求客户端
    提供通用的 GET/POST 请求能力，自动处理签名认证
    """

    def __init__(
        self,
        ak: str,
        sk: str,
        host="vod.volcengineapi.com",
        region="cn-north-1",
        service="vod",
    ):
        """
        初始化客户端

        Args:
            ak: 火山引擎 Access Key ID
            sk: 火山引擎 Access Key Secret
            host: 域名，默认 vod.volcengineapi.com
            region: 区域，默认 cn-north-1
            service: 服务名，默认 vod
        """
        self.ak = ak
        self.sk = sk
        self.host = host
        self.region = region
        self.service = service
        # 不打印 ak/sk，避免在日志中泄露敏感信息

    def get(self, action: str, version: str, params: dict = None) -> str:
        """
        发送 GET 请求

        Args:
            action: API 动作名称
            version: API 版本
            params: 请求参数

        Returns:
            响应文本
        """
        return self._request(action, params or {}, method="GET", version=version)

    def post(self, action: str, version: str, body: dict) -> str:
        """
        发送 POST 请求

        Args:
            action: API 动作名称
            version: API 版本
            body: 请求体

        Returns:
            响应文本
        """
        return self._request(action, body, method="POST", version=version)

    def _request(self, action: str, data: dict, method: str, version: str) -> str:
        """
        发送请求的核心方法

        Args:
            action: API 动作名称
            data: 请求数据
            method: 请求方法
            version: API 版本

        Returns:
            响应文本
        """
        base_url = f"https://{self.host}/"

        # GET: data 作为 query params；POST: data 作为 body
        query_params = {"Action": action, "Version": version}
        body_dict = {}
        if method == "GET":
            if data:
                query_params.update(data)
        else:
            body_dict = data or {}

        # canonical query string needs RFC3986 encoding + stable ordering
        canonical_query = urlencode(
            sorted(query_params.items()), quote_via=quote, safe="-_.~"
        )
        url = f"{base_url}?{canonical_query}"

        json_body = "" if method == "GET" else json.dumps(body_dict, ensure_ascii=False)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        bh = hashlib.sha256(json_body.encode()).hexdigest()

        # 构建头部
        h = {
            "content-type": "application/json; charset=utf-8",
            "host": self.host,
            "x-content-sha256": bh,
            "x-date": ts,
        }
        sk_list = sorted(h.keys())
        ch, sh = "".join(f"{k}:{h[k]}\n" for k in sk_list), ";".join(sk_list)
        cr = f"{method}\n/\n{canonical_query}\n{ch}\n{sh}\n{bh}"

        # 计算签名
        cs = f"{ts[:8]}/{self.region}/{self.service}/request"
        sts = f"HMAC-SHA256\n{ts}\n{cs}\n{hashlib.sha256(cr.encode()).hexdigest()}"
        sig = hmac.new(
            reduce(
                lambda k, v: hmac.new(k, v.encode(), hashlib.sha256).digest(),
                [ts[:8], self.region, self.service, "request"],
                self.sk.encode(),
            ),
            sts.encode(),
            hashlib.sha256,
        ).hexdigest()

        # 构建最终头部
        headers = {k.title().replace("X-C", "X-c"): v for k, v in h.items()}
        headers["Authorization"] = (
            f"HMAC-SHA256 Credential={self.ak}/{cs}, SignedHeaders={sh}, Signature={sig}"
        )

        # 发送请求
        if method == "GET":
            r = requests.get(url, headers=headers)
        else:
            r = requests.post(url, headers=headers, data=json_body.encode())

        if r.status_code != 200:
            raise Exception(f"HTTP {r.status_code}: {r.text}")
        return r.text
