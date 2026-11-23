"""读取远端配置，通过 A2A SDK 发送消息、查询任务和接收流式回复。"""

import asyncio
import os
from contextlib import aclosing, asynccontextmanager
from pathlib import Path

import httpx
from a2a.client.errors import (
    A2AClientError,
    A2AClientJSONRPCError,
    A2AClientTimeoutError,
)
from a2a.client.transports.jsonrpc import JsonRpcTransport
from a2a.server.request_handlers import RequestHandler
from a2a.types import AgentCard, InternalError, PushNotificationNotSupportedError
from a2a.utils.errors import ServerError
from pydantic import ValidationError


DIRECTORY = Path(__file__).resolve().parent
TIMEOUT = 60.0


class UpstreamTimeoutError(ServerError):
    def __init__(self):
        super().__init__(InternalError(message="Remote A2A request timed out"))


@asynccontextmanager
async def upstream_errors():
    try:
        async with asyncio.timeout(TIMEOUT):
            yield
    except A2AClientJSONRPCError as exc:
        raise ServerError(exc.error) from None
    except (TimeoutError, httpx.TimeoutException, A2AClientTimeoutError):
        raise UpstreamTimeoutError() from None
    except (A2AClientError, httpx.HTTPError, ValidationError):
        raise ServerError(InternalError(message="Remote A2A request failed")) from None


class A2ATool(RequestHandler):
    """把服务端收到的 A2A 请求直接交给远端 Agent。"""

    def __init__(self, *, card_path=None, http_transport=None):
        self.card_path = Path(
            card_path
            or os.getenv("REMOTE_AGENT_CARD_PATH", DIRECTORY / "remote_agentcard.json")
        )
        self.http_transport = http_transport
        self.remote_card: AgentCard | None = None
        self.client: JsonRpcTransport | None = None
        self.http_client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        try:
            card = AgentCard.model_validate_json(self.card_path.read_text())
        except (OSError, ValueError):
            raise RuntimeError(
                "Check remote_agentcard.json or REMOTE_AGENT_CARD_PATH"
            ) from None
        api_key = os.getenv("HI_AGENT_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("Set HI_AGENT_API_KEY to the Hi Agent A2A channel key")
        remote_url = card.url
        if (card.preferred_transport or "JSONRPC") != "JSONRPC":
            remote_url = next(
                (
                    item.url
                    for item in card.additional_interfaces or []
                    if item.transport == "JSONRPC"
                ),
                None,
            )
            if remote_url is None:
                raise RuntimeError("Remote Agent Card must support JSONRPC")
        self.remote_card = card
        self.http_client = httpx.AsyncClient(
            headers={"Apikey": api_key},
            timeout=TIMEOUT,
            transport=self.http_transport,
        )
        self.client = JsonRpcTransport(
            self.http_client, agent_card=card, url=remote_url
        )
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        if self.http_client is not None:
            await self.http_client.aclose()
        self.client = None
        self.http_client = None

    @staticmethod
    def extensions(context):
        return list(context.requested_extensions) if context else None

    async def on_message_send(self, params, context=None):
        """发送消息，等待远端返回结果。"""
        self._check_configuration(params)
        async with upstream_errors():
            return await self.client.send_message(
                params, extensions=self.extensions(context)
            )

    async def on_message_send_stream(self, params, context=None):
        """发送消息，逐条转发远端事件。"""
        self._check_configuration(params)
        async with upstream_errors():
            stream = self.client.send_message_streaming(
                params, extensions=self.extensions(context)
            )
            async with aclosing(stream):
                async for event in stream:
                    yield event

    async def on_get_task(self, params, context=None):
        async with upstream_errors():
            return await self.client.get_task(
                params, extensions=self.extensions(context)
            )

    async def on_cancel_task(self, params, context=None):
        async with upstream_errors():
            return await self.client.cancel_task(
                params, extensions=self.extensions(context)
            )

    async def on_resubscribe_to_task(self, params, context=None):
        async with upstream_errors():
            stream = self.client.resubscribe(
                params, extensions=self.extensions(context)
            )
            async with aclosing(stream):
                async for event in stream:
                    yield event

    @staticmethod
    def _check_configuration(params):
        if params.configuration and params.configuration.push_notification_config:
            raise ServerError(PushNotificationNotSupportedError())

    async def on_set_task_push_notification_config(self, params, context=None):
        # SDK 要求实现这些方法；当前服务不使用推送通知。
        raise ServerError(PushNotificationNotSupportedError())

    async def on_get_task_push_notification_config(self, params, context=None):
        raise ServerError(PushNotificationNotSupportedError())

    async def on_list_task_push_notification_config(self, params, context=None):
        raise ServerError(PushNotificationNotSupportedError())

    async def on_delete_task_push_notification_config(self, params, context=None):
        raise ServerError(PushNotificationNotSupportedError())
