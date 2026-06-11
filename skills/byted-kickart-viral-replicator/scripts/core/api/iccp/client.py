# Copyright 2026 ByteDance
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


from abc import ABC, abstractmethod
import sys
import os
import time
import logging
import requests
from collections import defaultdict
from urllib.parse import urlencode, urlparse

# 动态加载项目根目录，以便于引入 core
sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
)
from core.utils.hash import HashUtils
from core.auth.strategy import AuthType, AuthStrategy


class IccpClient(ABC):
    @abstractmethod
    def do_request(self, method: str, queries: dict, body: bytes, action: str) -> dict:
        pass


class V1IccpClient(IccpClient):
    """基于 AK/SK 的请求客户端 (Strategy 实现)"""

    ADDR = "https://icp.volcengineapi.com"
    SERVICE = "iccloud_muse"
    REGION = "cn-north"
    VERSION = "2025-11-25"

    def __init__(self):
        self.ak = os.getenv("ACCESS_KEY_ID") or ""
        self.sk = os.getenv("SECRET_ACCESS_KEY") or ""

    def _get_signed_key(
        self, secret_key: str, date: str, region: str, service: str
    ) -> bytes:
        k_date = HashUtils.hmac_sha256(secret_key.encode("utf-8"), date)
        k_region = HashUtils.hmac_sha256(k_date, region)
        k_service = HashUtils.hmac_sha256(k_region, service)
        return HashUtils.hmac_sha256(k_service, "request")

    def do_request(self, method: str, queries: dict, body: bytes, action: str) -> dict:
        queries["Action"] = action
        queries["Version"] = self.VERSION

        query_string = urlencode(queries).replace("+", "%20")
        url = f"{self.ADDR}?{query_string}"

        date = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(time.time()))
        auth_date = date[:8]
        payload = HashUtils.hash_sha256(body).hex()

        signed_headers = ["host", "x-date", "x-content-sha256", "content-type"]
        host = urlparse(self.ADDR).netloc

        header_list = [
            f"host:{host}",
            f"x-date:{date}",
            f"x-content-sha256:{payload}",
            "content-type:application/json",
        ]
        header_string = "\n".join(header_list)

        canonical_string = "\n".join(
            [
                method.upper(),
                "/",
                query_string,
                f"{header_string}\n",
                ";".join(signed_headers),
                payload,
            ]
        )
        hashed_canonical_string = HashUtils.hash_sha256(
            canonical_string.encode("utf-8")
        ).hex()

        credential_scope = f"{auth_date}/{self.REGION}/{self.SERVICE}/request"
        sign_string = "\n".join(
            ["HMAC-SHA256", date, credential_scope, hashed_canonical_string]
        )

        signed_key = self._get_signed_key(self.sk, auth_date, self.REGION, self.SERVICE)
        signature = HashUtils.hmac_sha256(signed_key, sign_string).hex()

        authorization = (
            f"HMAC-SHA256 Credential={self.ak}/{credential_scope},"
            f" SignedHeaders={';'.join(signed_headers)},"
            f" Signature={signature}"
        )

        headers = defaultdict(str)
        headers["X-Date"] = date
        headers["X-Content-Sha256"] = payload
        headers["Content-Type"] = "application/json"
        headers["Authorization"] = authorization

        if ppe_env := os.getenv("X_VOLC_ENV"):
            headers.update(
                {"X-TT-Env": "ppe_volcengine", "X-Volc-Env": ppe_env, "X-Use-Ppe": "1"}
            )

        logging.info(f">>> {method.upper()} {url} {body}")
        response = requests.request(
            method=method.upper(), url=url, headers=headers, data=body, timeout=30
        )
        logging.info(f"<<< {response.headers} {response.text}")
        return response.json()


class V2IccpClient(IccpClient):
    """基于 Ark Token 的请求客户端 (Strategy 实现)"""

    SERVICE = "iccloud_muse"
    REGION = "cn-north"
    VERSION = "2025-11-25"

    def __init__(self):
        self.addr = os.getenv("ARK_SKILL_API_BASE")
        self.token = os.getenv("ARK_SKILL_API_KEY") or ""

    def do_request(self, method: str, queries: dict, body: bytes, action: str) -> dict:
        queries["Action"] = action
        queries["Version"] = V2IccpClient.VERSION

        query_string = urlencode(queries).replace("+", "%20")
        url = f"{self.addr}?{query_string}"

        headers = defaultdict(str)
        headers["Authorization"] = f"Bearer {self.token}"
        headers["Content-Type"] = "application/json"
        headers["ServiceName"] = V2IccpClient.SERVICE

        if ppe_env := os.getenv("X_VOLC_ENV"):
            headers.update(
                {"X-TT-Env": "ppe_volcengine", "X-Volc-Env": ppe_env, "X-Use-Ppe": "1"}
            )

        logging.info(f">>> {method.upper()} {url} {body}")
        response = requests.request(
            method=method.upper(), url=url, headers=headers, data=body, timeout=30
        )
        logging.info(f"<<< {response.headers} {response.text}")
        return response.json()


class IccpClientFactory:
    @staticmethod
    def create(strategy: AuthStrategy) -> IccpClient:
        if strategy.strategy == AuthType.API_KEY:
            return V2IccpClient()
        if strategy.strategy == AuthType.AK_SK:
            return V1IccpClient()
        raise ValueError(f"不支持的认证策略类型: {strategy.strategy}")
