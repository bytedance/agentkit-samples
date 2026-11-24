"""直连 Harness App 与通过 APIG 访问会话服务的两类数据面客户端。"""

import json
import time
import uuid
from urllib.parse import quote, urlsplit

import requests
from _clients import DataPlaneClient
from _common import redact


def request(method, base, path, headers, *, allowed=(), **kwargs):
    """保留网关路径前缀，不跟随重定向，也不输出服务端错误正文。"""
    try:
        response = requests.request(
            method,
            base.rstrip("/") + path,
            headers=headers,
            timeout=(10, 90),
            allow_redirects=False,
            **kwargs,
        )
    except requests.RequestException:
        raise RuntimeError(f"{method} {path}: 网络请求失败") from None
    if not (200 <= response.status_code < 300 or response.status_code in allowed):
        status = response.status_code
        response.close()
        raise RuntimeError(f"{method} {path}: HTTP {status}")
    return response


def events(response):
    """按 SSE 空行边界拼接多行 data，忽略心跳；断流由调用者判定。"""
    if response.headers.get("Content-Type", "").split(";")[0] != "text/event-stream":
        raise RuntimeError("响应不是 SSE")
    lines = []
    deadline = time.monotonic() + 300
    try:
        for line in response.iter_lines(chunk_size=1):
            if time.monotonic() > deadline:
                raise TimeoutError("等待本轮结束超时；不要直接重发消息")
            if line.startswith(b"data:"):
                lines.append(line[5:].lstrip())
            elif line.startswith(b"event:") and line[6:].strip() == b"error":
                raise RuntimeError("服务端返回 SSE error")
            elif not line and lines:
                payload = b"\n".join(lines)
                lines.clear()
                if payload == b"[DONE]":
                    return
                event = json.loads(payload)
                if not isinstance(event, dict):
                    raise RuntimeError("SSE data 不是 JSON 对象")
                yield event
    except requests.RequestException:
        raise RuntimeError("SSE 连接中断；不要直接重发消息") from None


def show(event, *secrets):
    """保留工具调用与结果供读者核对，隐藏已知凭据。"""
    text = json.dumps(redact(event), ensure_ascii=False)
    for secret in secrets:
        if secret:
            text = text.replace(secret, "<redacted>")
    print(text, flush=True)


class HarnessApp:
    """从 GetRuntime 读取 Runtime Key；仅访问 Runtime 自己的会话接口。"""

    def __init__(self, runtime):
        endpoint = runtime.get("Endpoint") or ""
        url = urlsplit(endpoint)
        if (
            runtime.get("Status") != "Ready"
            or url.scheme != "https"
            or not url.hostname
            or url.username is not None
            or url.query
            or url.fragment
        ):
            raise RuntimeError("GetRuntime 未返回 Ready 的 HTTPS Endpoint")
        key_auth = (runtime.get("AuthorizerConfiguration") or {}).get("KeyAuth") or {}
        self.key = key_auth.get("ApiKey")
        if not self.key or key_auth.get("ApiKeyLocation", "header").lower() != "header":
            raise RuntimeError("本示例要求 Runtime 的 Header KeyAuth")
        self.base = endpoint
        name = key_auth.get("ApiKeyName") or "x-api-key"
        self.headers = (
            {"Authorization": f"Bearer {self.key}"}
            if name.lower() == "authorization"
            else {name: self.key}
        )

    def call(self, method, path, *, allowed=(), **kwargs):
        """仅在 401 时按 Runtime 网关的 Bearer 约定重试。"""
        bearer = {"Authorization": f"Bearer {self.key}"}
        headers = {
            **self.headers,
            "Accept": "text/event-stream"
            if kwargs.get("stream")
            else "application/json",
        }
        response = request(
            method, self.base, path, headers, allowed=(*allowed, 401), **kwargs
        )
        if response.status_code != 401:
            return response
        response.close()
        if self.headers == bearer:
            raise RuntimeError(f"{method} {path}: HTTP 401")
        self.headers = bearer
        headers = {**bearer, "Accept": headers["Accept"]}
        return request(method, self.base, path, headers, allowed=allowed, **kwargs)

    @staticmethod
    def session_path(session):
        """按 Runtime 的 app/user/session 组合定位会话。"""
        app, user, session_id = (
            quote(session[key], safe="") for key in ("app_name", "user_id", "id")
        )
        return f"/apps/{app}/users/{user}/sessions/{session_id}"

    def create_session(self, session):
        """创建指定 ID 的会话；400/409 仅在确认会话存在后可继续。"""
        with self.call("GET", "/list-apps") as response:
            apps = response.json()
        if not isinstance(apps, list) or session["app_name"] not in apps:
            raise RuntimeError("Runtime 未发布 harness_agent；检查部署镜像")
        path = self.session_path(session)
        with self.call("POST", path, json={}, allowed=(400, 409)) as response:
            duplicate = response.status_code in {400, 409}
        if duplicate:
            with self.call("GET", path):
                pass

    def run_sse(self, session, prompt, secrets=()):
        """发送一轮用户消息并消费 Harness App 的 ADK 事件。"""
        payload = {
            "app_name": session["app_name"],
            "user_id": session["user_id"],
            "session_id": session["id"],
            "new_message": {"role": "user", "parts": [{"text": prompt}]},
            "streaming": True,
        }
        final_text = False
        with self.call("POST", "/run_sse", json=payload, stream=True) as response:
            for event in events(response):
                if (
                    event.get("error")
                    or event.get("errorCode")
                    or event.get("error_code")
                ):
                    raise RuntimeError("Harness App 执行失败")
                parts = (event.get("content") or {}).get("parts") or []
                if not event.get("partial") and any(
                    part.get("text") and not part.get("thought") for part in parts
                ):
                    final_text = True
                show(event, self.key, *secrets)
        if not final_text:
            raise RuntimeError("SSE 已关闭，但没有收到完整的模型文本事件")


def run_queue_sse(base, key, session_id, prompt, *, on_event=None):
    """提交消息后按回执序号订阅；收到回复与 end_turn 才算成功。"""
    data = DataPlaneClient(base, key)
    path = f"/v1/sessions/{quote(session_id, safe='')}/events"
    event_id = f"event-send-{uuid.uuid4().hex}"
    sent = data.call(
        "POST",
        path,
        body={
            "events": [
                {
                    "id": event_id,
                    "type": "user.message",
                    "content": [{"type": "text", "text": prompt}],
                }
            ]
        },
    )
    accepted = next(
        (evt for evt in (sent.get("data") or []) if evt.get("id") == event_id),
        {},
    )
    cursor = accepted.get("sequence")
    if not isinstance(cursor, int) or cursor <= 0:
        raise RuntimeError("消息回执缺少 sequence；请检查会话事件，勿直接重发")
    saw_answer = False
    with request(
        "GET",
        data.base_url,
        path + "/stream",
        {"x-api-key": key, "Accept": "text/event-stream"},
        params={"after_sequence": cursor},
        stream=True,
    ) as response:
        for event in events(response):
            show(event, key)
            if on_event is not None and on_event(event):
                return
            kind = event.get("type")
            if kind in {"agent.error", "session.error", "session.status_terminated"}:
                raise RuntimeError(f"会话执行结束：{kind}")
            if kind == "agent.message":
                content = event.get("content") or []
                saw_answer |= isinstance(content, list) and any(
                    isinstance(part, dict) and part.get("text") for part in content
                )
            if kind == "session.status_idle":
                reason = (event.get("stop_reason") or {}).get("type")
                if reason == "requires_action":
                    raise RuntimeError("会话需要客户端额外处理")
                if reason == "end_turn":
                    if saw_answer:
                        return
                    break
    raise RuntimeError("未收到完整回复和 end_turn；请检查会话事件")
