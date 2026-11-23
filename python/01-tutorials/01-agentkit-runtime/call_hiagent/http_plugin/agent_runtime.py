"""连接远端 AgentKit Runtime，调用接口并读取 ADK 事件。"""

import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from urllib.parse import quote

import httpx
from dotenv import load_dotenv
from fastapi import HTTPException
from httpx_sse import EventSource

from plugin_models import PluginRequest


DIRECTORY = Path(__file__).resolve().parent
load_dotenv(DIRECTORY / ".env")


def runtime_client() -> httpx.AsyncClient:
    base_url = os.environ["UPSTREAM_BASE_URL"].rstrip("/")
    key = os.getenv("UPSTREAM_API_KEY", "").strip()
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    return httpx.AsyncClient(
        base_url=base_url + "/", headers=headers, timeout=httpx.Timeout(60, connect=10)
    )


async def ensure_session(
    client: httpx.AsyncClient, app_name: str, body: PluginRequest
) -> None:
    app = quote(app_name, safe="")
    user = quote(body.user_id, safe="")
    session = quote(body.session_id, safe="")
    response = await client.post(f"apps/{app}/users/{user}/sessions/{session}", json={})
    if response.status_code != 409:  # 409 表示会话已经存在，可以继续使用。
        response.raise_for_status()


@contextmanager
def runtime_request(client: httpx.AsyncClient) -> Iterator[None]:
    """检查上游凭证，并将 Runtime 错误映射成插件 HTTP 状态码。"""
    if "Authorization" not in client.headers:
        raise HTTPException(
            503, "插件缺少远端 Agent 的 API Key，请设置 UPSTREAM_API_KEY"
        )
    try:
        yield
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        raise HTTPException(
            status if status >= 400 else 502, f"上游 Runtime 返回 HTTP {status}"
        ) from exc
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(502, "上游回复格式无效") from exc
    except httpx.TimeoutException as exc:
        raise HTTPException(504, "上游 Runtime 请求超时") from exc
    except httpx.RequestError as exc:
        raise HTTPException(502, "与上游 Runtime 的连接失败") from exc


async def fetch_agent_card(client: httpx.AsyncClient) -> dict:
    with runtime_request(client):
        response = await client.get(
            ".well-known/agent-card.json", headers={"Accept": "application/json"}
        )
        response.raise_for_status()
        card = response.json()
        if not isinstance(card, dict):
            raise HTTPException(502, "上游 Agent Card 应为 JSON 对象")

        # SDK 默认可能公布 localhost。已签名的卡片需要保留原文。
        if not card.get("signatures") and card.get("url"):
            address = httpx.URL(card["url"])
            if address.host in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}:
                relative_path = "./" + address.raw_path.decode("ascii").lstrip("/")
                card["url"] = str(client.base_url.join(relative_path))
        return card


@asynccontextmanager
async def open_agent_response(
    client: httpx.AsyncClient, endpoint: str, body: PluginRequest
) -> AsyncIterator[httpx.Response]:
    headers = {
        "Accept": "application/json" if endpoint == "run" else "text/event-stream"
    }
    with runtime_request(client):
        if endpoint == "invoke":
            headers.update(user_id=body.user_id, session_id=body.session_id)
            payload = {"prompt": body.message}
        else:
            app_name = os.getenv("UPSTREAM_APP_NAME", "simple_agent")
            await ensure_session(client, app_name, body)
            payload = {
                "app_name": app_name,
                "user_id": body.user_id,
                "session_id": body.session_id,
                "new_message": {"role": "user", "parts": [{"text": body.message}]},
                "streaming": endpoint == "run_sse" and body.streaming is not False,
            }

        async with client.stream(
            "POST", endpoint, json=payload, headers=headers
        ) as response:
            response.raise_for_status()
            yield response


async def agent_events(response: httpx.Response) -> AsyncIterator[dict]:
    media_type = (
        response.headers.get("content-type", "").partition(";")[0].strip().lower()
    )
    if media_type == "text/event-stream":
        async for frame in EventSource(response).aiter_sse():
            if frame.event == "error":
                raise HTTPException(502, "上游 Runtime 返回了错误事件")
            if frame.data == "[DONE]":
                break
            if frame.data:
                yield frame.json()
    else:
        await response.aread()
        events = response.json()
        if not isinstance(events, list):
            raise HTTPException(502, "上游 Runtime 未返回 ADK 事件列表")
        for event in events:
            yield event
