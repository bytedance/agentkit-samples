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

# ============================================================
# Monkey patch: 修复 veadk 0.2.22 的 RuntimeError bug
# ============================================================
import sys

# ============================================================
# 正常的导入和代码
# ============================================================

import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

from veadk import Agent
from veadk.integrations.ve_identity import (
    AuthRequestProcessor,
    VeIdentityFunctionTool,
    oauth2_auth,
)
from veadk.integrations.ve_identity.auth_mixins import OAuth2AuthMixin
from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.tool_context import ToolContext

from veadk import Runner
from agentkit.apps import AgentkitSimpleApp
from typing import AsyncGenerator

from veadk.integrations.ve_identity import (
    is_pending_auth_event,
    get_function_call_id,
    get_function_call_auth_config,
)
from google.adk.events.event import Event
from google.adk.utils.context_utils import Aclosing
from google.genai import types

load_dotenv(Path(__file__).parent / ".env")


def _patched_patch_google_adk_telemetry():
    """修复版本的 patch_google_adk_telemetry，避免 RuntimeError"""
    try:
        from google.adk.agents.callback_context import CallbackContext
        from google.adk.tools.tool_context import ToolContext
    except ImportError:
        return

    for mod_name, mod in list(sys.modules.items()):
        if mod_name.startswith("google.adk") and mod:
            for attr_name in dir(mod):
                try:
                    obj = getattr(mod, attr_name, None)
                    if isinstance(obj, type) and issubclass(
                        obj, (CallbackContext, ToolContext)
                    ):
                        if not hasattr(obj, "_veadk_span"):
                            obj._veadk_span = property(
                                lambda self: getattr(self.state, "_veadk_span", None),
                                lambda self, v: setattr(self.state, "_veadk_span", v),
                            )
                except (TypeError, AttributeError):
                    pass


try:
    import veadk.utils.patches

    veadk.utils.patches.patch_google_adk_telemetry = _patched_patch_google_adk_telemetry
except ImportError:
    pass

# 从环境变量读取凭证提供者名称
FEISHU_CREDENTIAL_PROVIDER = os.getenv("FEISHU_CREDENTIAL_PROVIDER", "feishu_oauth")

print(f"[CONFIG] FEISHU_CREDENTIAL_PROVIDER={FEISHU_CREDENTIAL_PROVIDER}")

# ============================================================
# 飞书 API 工具
# ============================================================


async def feishu_get_document(document_id: str, *, access_token: str) -> str:
    """
    获取飞书文档的内容并总结

    Args:
        document_id: 飞书文档 ID（从文档 URL 中获取，如 https://xxx.feishu.cn/docx/ABC123 中的 ABC123）
        access_token: 飞书 OAuth access_token（由凭证托管自动注入）

    Returns:
        文档内容的纯文本
    """
    try:
        print(f"[飞书] 获取文档 {document_id}, Token: {access_token[:8]}...")

        async with httpx.AsyncClient() as client:
            # 获取文档纯文本内容
            response = await client.get(
                f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/raw_content",
                headers={
                    "Authorization": f"Bearer {access_token}",
                },
            )

            if response.status_code != 200:
                error_data = response.json()
                return f"飞书 API 错误: {response.status_code} - {error_data.get('msg', response.text)}"

            data = response.json()
            if data.get("code") != 0:
                return f"飞书 API 错误: {data.get('code')} - {data.get('msg')}"

            content = data.get("data", {}).get("content", "")
            return f"文档内容:\n{content}"

    except Exception as e:
        return f"获取飞书文档出错: {str(e)}"


# 使用凭证托管包装飞书工具
feishu_doc_tool = VeIdentityFunctionTool(
    func=feishu_get_document,
    auth_config=oauth2_auth(
        provider_name=FEISHU_CREDENTIAL_PROVIDER,
        auth_flow="USER_FEDERATION",
    ),
)

# ============================================================
# 凭证清理工具（用于重新触发授权）
# ============================================================


async def clean_feishu_state(
    args: dict[str, Any], *, tool_context: ToolContext
) -> None:
    """
    清理用户的飞书 OAuth 身份凭据

    用户可以通过说"重新授权飞书"来重新触发飞书授权流程。
    """
    oauth_client = OAuth2AuthMixin(
        provider_name=FEISHU_CREDENTIAL_PROVIDER,
        auth_flow="USER_FEDERATION",
        force_authentication=True,
    )
    await oauth_client._get_oauth2_token_or_auth_url(tool_context=tool_context)
    return None


clean_feishu_tool = FunctionTool(clean_feishu_state)

# ============================================================
# Agent 定义
# ============================================================

agent: Agent = Agent(
    name="larkdoc_assistant",
    tools=[
        # 飞书工具
        feishu_doc_tool,
        # 凭证清理工具
        clean_feishu_tool,
    ],
    run_processor=AuthRequestProcessor(),
    tracers=[],
    instruction="""您是一个飞书文档助手，能够帮助用户访问飞书的资源。

## 飞书功能
1. **获取文档内容** - 使用 feishu_get_document 获取飞书文档内容（需要文档 ID）

## 使用示例
- "帮我总结这个飞书文档: ABC123"

## 重新授权
- 说"重新授权飞书"可以重新触发飞书授权
""",
)

app = AgentkitSimpleApp()
app_name = "simple_streamable_app"
runner = Runner(app_name=app_name, agent=agent)


@app.entrypoint
async def run(payload: dict, headers: dict) -> AsyncGenerator[Event, None]:
    prompt = payload.get("prompt", "")
    user_id = headers.get("user_id", "anonymous")
    session_id = headers.get("session_id", "default")

    processor = AuthRequestProcessor()
    session_service = runner.short_term_memory.session_service  # type: ignore
    session = await session_service.get_session(
        app_name=app_name, user_id=user_id, session_id=session_id
    )
    if not session:
        await session_service.create_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )

    current_message = types.Content(role="user", parts=[types.Part(text=prompt)])

    while True:
        pending_auth = False

        async with Aclosing(
            runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=current_message,
            )
        ) as agen:
            async for event in agen:
                sse_event = event.model_dump_json(exclude_none=True, by_alias=True)
                yield sse_event

                if is_pending_auth_event(event):
                    auth_request_event_id = get_function_call_id(event)
                    auth_config = get_function_call_auth_config(event)
                    current_message = await processor.process_auth_request(
                        auth_request_event_id, auth_config
                    )
                    pending_auth = True
                    break

        if not pending_auth:
            break


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
