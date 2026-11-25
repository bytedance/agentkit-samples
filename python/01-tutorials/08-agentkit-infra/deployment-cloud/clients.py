"""独立的 TOP 签名客户端及 Cloud Runtime Session 客户端。"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import quote, urlencode, urlsplit

import requests

CREDENTIAL_FIELDS = (
    "access_key",
    "secret_key",
    "session_token",
)

WORKSPACE_ACTIONS = {
    "CreateEnvironment",
    "GetEnvironment",
    "ListEnvironmentResources",
    "GetEnvironmentResource",
    "CreateRuntimeTemplate",
    "CreateHarness",
    "GetHarness",
    "CreateDeployment",
}


class APIError(RuntimeError):
    """保留错误码和请求 ID，不包含可能携带凭据的服务端正文。"""

    def __init__(
        self,
        operation: str,
        status: int,
        code: str = "",
        request_id: str = "",
        message: str = "",
    ):
        super().__init__(
            f"{operation}: HTTP {status}, code={code}, request_id={request_id}"
            + (f", {message}" if message else "")
        )
        self.status = status
        self.code = code


def digest(key: bytes, value: str) -> bytes:
    """输入字符串并返回 HMAC-SHA256，供 TOP 分层派生签名密钥。"""
    return hmac.new(key, value.encode(), hashlib.sha256).digest()


class TopClient:
    """使用账号 AK/SK 签名请求；Workspace 选择器在签名前注入。"""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.audit: list[dict[str, Any]] = []

    def call(self, action: str, body: dict[str, Any]) -> dict[str, Any]:
        """读取请求在明确的临时 Workspace 查找故障时有限重试；写操作不重放。"""
        for attempt in range(3):
            try:
                return self._call_once(action, body)
            except APIError as exc:
                if (
                    not action.startswith(("Get", "List"))
                    or "Workspace lookup is unavailable" not in str(exc)
                    or attempt == 2
                ):
                    raise
                time.sleep(2 * (attempt + 1))
        raise RuntimeError("TOP 读取失败")

    def _call_once(self, action: str, body: dict[str, Any]) -> dict[str, Any]:
        """调用一次 TOP；不自动重发写请求，调用者使用持久化 ClientToken 恢复。"""
        cfg = self.config
        body = dict(body)
        if cfg.get("workspace_id") and action in WORKSPACE_ACTIONS:
            body["WorkspaceId"] = cfg["workspace_id"]
        data = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode()
        query = urlencode(sorted({"Action": action, "Version": "2025-10-30"}.items()))
        now = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
        payload_hash = hashlib.sha256(data).hexdigest()
        signed = {
            "content-type": "application/json",
            "host": cfg["host"],
            "x-content-sha256": payload_hash,
            "x-date": now,
        }
        if cfg.get("session_token"):
            signed["x-security-token"] = cfg["session_token"]
        names = ";".join(sorted(signed))
        canonical = "\n".join(
            [
                "POST",
                "/",
                query,
                "".join(f"{key}:{signed[key]}\n" for key in sorted(signed)),
                names,
                payload_hash,
            ]
        )
        scope = f"{now[:8]}/{cfg['region']}/agentkit/request"
        to_sign = "\n".join(
            [
                "HMAC-SHA256",
                now,
                scope,
                hashlib.sha256(canonical.encode()).hexdigest(),
            ]
        )
        key = cfg["secret_key"].encode()
        for part in (now[:8], cfg["region"], "agentkit", "request"):
            key = digest(key, part)
        signed["Authorization"] = (
            f"HMAC-SHA256 Credential={cfg['access_key']}/{scope}, "
            f"SignedHeaders={names}, Signature={digest(key, to_sign).hex()}"
        )
        try:
            with requests.post(
                f"https://{cfg['host']}/?{query}",
                data=data,
                headers=signed,
                timeout=(10, 90),
                allow_redirects=False,
            ) as response:
                payload = response.json()
                if not isinstance(payload, dict):
                    raise RuntimeError(f"{action}: TOP 响应不是 JSON 对象")
                meta = payload.get("ResponseMetadata") or {}
                error = meta.get("Error") or {}
                self.audit.append(
                    {
                        "action": action,
                        "status": response.status_code,
                        "request_id": meta.get("RequestId", ""),
                    }
                )
                if not 200 <= response.status_code < 300 or error:
                    message = str(error.get("Message") or "")[:512]
                    for field in CREDENTIAL_FIELDS:
                        if cfg.get(field):
                            message = message.replace(cfg[field], "<redacted>")
                    raise APIError(
                        action,
                        response.status_code,
                        error.get("Code", ""),
                        meta.get("RequestId", ""),
                        message,
                    )
                result = payload.get("Result", payload)
                if not isinstance(result, dict):
                    raise RuntimeError(f"{action}: 响应缺少对象")
                return result
        except (requests.RequestException, ValueError):
            raise RuntimeError(
                f"{action}: 请求失败或响应无效；请沿用原 ClientToken 恢复"
            ) from None


class RuntimeClient:
    """仅使用 GetRuntime 的 Endpoint 和 Header KeyAuth 访问 Harness App。"""

    def __init__(self, runtime: dict[str, Any]):
        self.base = runtime.get("Endpoint") or ""
        url = urlsplit(self.base)
        auth = (runtime.get("AuthorizerConfiguration") or {}).get("KeyAuth") or {}
        if (
            runtime.get("Status") != "Ready"
            or url.scheme != "https"
            or not url.hostname
            or url.username
            or url.query
            or url.fragment
        ):
            raise RuntimeError("Runtime 必须 Ready 且返回合法 HTTPS Endpoint")
        if auth.get("ApiKeyLocation", "header").lower() != "header" or not auth.get(
            "ApiKey"
        ):
            raise RuntimeError("Runtime 必须提供 Header KeyAuth")
        self.key = auth["ApiKey"]
        name = auth.get("ApiKeyName") or "x-api-key"
        self.headers = {
            name: f"Bearer {self.key}" if name.lower() == "authorization" else self.key
        }

    def request(
        self, method: str, path: str, *, allowed: tuple[int, ...] = (), **kwargs: Any
    ):
        """禁止重定向；仅在 401 尚未执行时尝试 Bearer 鉴权。"""
        for attempt in range(2):
            try:
                response = requests.request(
                    method,
                    self.base.rstrip("/") + path,
                    headers=self.headers,
                    timeout=(10, 90),
                    allow_redirects=False,
                    **kwargs,
                )
            except requests.RequestException:
                raise RuntimeError(
                    f"{method} {path}: 网络失败；执行请求请勿直接重发"
                ) from None
            if response.status_code == 401 and attempt == 0:
                response.close()
                self.headers = {"Authorization": f"Bearer {self.key}"}
                continue
            if not response.ok or 300 <= response.status_code < 400:
                if response.status_code not in allowed:
                    status = response.status_code
                    response.close()
                    raise APIError(f"{method} {path}", status)
            return response
        raise RuntimeError("Runtime 鉴权失败")

    def json(self, method: str, path: str, **kwargs: Any) -> Any:
        """读取 JSON 并关闭连接，不输出 Runtime Key 或完整响应。"""
        with self.request(method, path, **kwargs) as response:
            return response.json()

    @staticmethod
    def path(app: str, user: str, session_id: str) -> str:
        """对 app/user/session 三个路径选择器分别编码。"""
        return f"/apps/{quote(app, safe='')}/users/{quote(user, safe='')}/sessions/{quote(session_id, safe='')}"

    def run(
        self, app: str, user: str, session_id: str, prompt: str
    ) -> list[dict[str, Any]]:
        """只发送第二轮，按 SSE 帧读取；断流不自动重发。"""
        payload = {
            "app_name": app,
            "user_id": user,
            "session_id": session_id,
            "new_message": {"role": "user", "parts": [{"text": prompt}]},
            "streaming": True,
        }
        events = []
        lines: list[str] = []
        with self.request("POST", "/run_sse", json=payload, stream=True) as response:
            if (
                response.headers.get("Content-Type", "").split(";")[0]
                != "text/event-stream"
            ):
                raise RuntimeError("Runtime 未返回 SSE")
            try:
                for line in response.iter_lines(decode_unicode=True, chunk_size=1):
                    if line.startswith("data:"):
                        lines.append(line[5:].lstrip())
                    elif line.startswith("event:") and line[6:].strip() == "error":
                        raise RuntimeError("Runtime SSE 返回 error")
                    elif not line and lines:
                        text = "\n".join(lines)
                        lines.clear()
                        if text == "[DONE]":
                            break
                        event = json.loads(text)
                        if not isinstance(event, dict) or any(
                            event.get(k) for k in ("error", "errorCode", "error_code")
                        ):
                            raise RuntimeError("Runtime SSE 执行失败")
                        events.append(event)
                if lines:
                    raise RuntimeError("SSE 在完整帧结束前断开")
            except requests.RequestException:
                raise RuntimeError(
                    "SSE 断流；请只读检查 Session，勿直接重发第二轮"
                ) from None
        if not events:
            raise RuntimeError("Runtime SSE 未返回事件")
        return events
