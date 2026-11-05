"""通过日志服务 REST API 准备观测资源，复用教程的账号签名。"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

import requests
from _clients import ControlConfig, HarnessInfraError, sign_headers


class TlsClient:
    """访问当前地域的 TLS 公网入口，不将账号凭据写入状态或错误日志。"""

    def __init__(self, config: ControlConfig) -> None:
        """将控制面配置转换为日志服务签名配置，保留临时凭据。"""
        self.config = replace(
            config,
            service="TLS",
            host=f"tls-{config.region}.volces.com",
            scheme="https",
        )

    def call(
        self, action: str, body: dict[str, Any], *, method: str = "POST"
    ) -> dict[str, Any]:
        """发送原生 REST 请求；创建失败后由部署状态和名称查询恢复。"""
        path = f"/{action}"
        query = body if method == "GET" else {}
        payload = json.dumps(
            {} if method == "GET" else body, ensure_ascii=False, separators=(",", ":")
        ).encode()
        headers = sign_headers(
            method,
            self.config.host,
            query,
            payload,
            config=self.config,
            path=path,
        )
        headers["x-tls-apiversion"] = "0.3.0"
        try:
            response = requests.request(
                method,
                f"https://{self.config.host}{path}",
                params=query,
                data=payload,
                headers=headers,
                timeout=60,
                allow_redirects=False,
            )
        except requests.RequestException:
            raise RuntimeError(
                f"TLS {action}: network error; rerun with the same backend state"
            ) from None
        request_id = response.headers.get("x-tls-requestid", "")
        try:
            result = response.json()
        except ValueError:
            result = None
        if not isinstance(result, dict):
            raise HarnessInfraError(
                f"TLS {action}",
                "InvalidResponse",
                "response must be a JSON object",
                status_code=response.status_code,
                request_id=request_id,
            )
        code = result.get("ErrorCode") or result.get("Code")
        if code or not 200 <= response.status_code < 300:
            raise HarnessInfraError(
                f"TLS {action}",
                str(code or "HTTPError"),
                str(result.get("ErrorMessage") or result.get("Message") or ""),
                status_code=response.status_code,
                request_id=request_id,
            )
        return result
