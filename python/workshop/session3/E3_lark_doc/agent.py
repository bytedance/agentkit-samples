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

from typing import Any

from veadk import Agent
import json

import lark_oapi as lark
from lark_oapi.api.docx.v1 import (
    RawContentDocumentRequest,
    RawContentDocumentResponse,
)
from lark_oapi.core.model import RequestOption
from veadk.integrations.ve_identity import (
    VeIdentityFunctionTool,
    AuthRequestProcessor,
    oauth2_auth,
)
from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.tool_context import ToolContext
from veadk.integrations.ve_identity.auth_mixins import OAuth2AuthMixin
from veadk.memory.short_term_memory import ShortTermMemory

short_term_memory = ShortTermMemory(backend="local")


async def lark_document_query(document_id: str, *, access_token: str) -> str:
    """
    查询飞书文档内容

    Args:
        document_id: 飞书文档ID（从文档链接中提取的最后一部分）
        access_token: 飞书 API OAuth2.0 访问令牌

    Returns:
        文档内容的JSON字符串
    """
    try:
        print(f"查询飞书文档: {document_id}")
        print(f"使用访问令牌: {access_token[:8]}...")

        client = (
            lark.Client.builder()
            .enable_set_token(True)
            .log_level(lark.LogLevel.INFO)
            .build()
        )
        request: RawContentDocumentRequest = (
            RawContentDocumentRequest.builder().lang(0).document_id(document_id).build()
        )

        response: RawContentDocumentResponse = client.docx.v1.document.raw_content(
            request, RequestOption.builder().user_access_token(access_token).build()
        )

        if not response.success():
            lark.logger.error(
                f"client.docx.v1.document.raw_content failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}"
            )
            return f"文档查询失败: {response.msg}"

        # 处理业务结果
        return lark.JSON.marshal(response.data, indent=4)

    except Exception as e:
        return f"文档查询出错: {str(e)}"


# 创建使用 OAuth2 认证的飞书文档查询工具
lark_doc_tool = VeIdentityFunctionTool(
    func=lark_document_query,
    auth_config=oauth2_auth(
        provider_name="feishu",
        auth_flow="USER_FEDERATION",
    ),
)


async def clean_state(args: dict[str, Any], *, tool_context: ToolContext) -> None:
    """Clean user's Oauth identity state.

    Args:
        args: fixed arguments for cleaning identity state: {"op": "clean"}
    """
    oauth_client = OAuth2AuthMixin(
        provider_name="feishu",
        auth_flow="USER_FEDERATION",
        force_authentication=True,
    )
    await oauth_client._get_oauth2_token_or_auth_url(tool_context=tool_context)
    return None


clean_state_tool = FunctionTool(clean_state)

agent: Agent = Agent(
    name="lark_doc",
    tools=[lark_doc_tool, clean_state_tool],
    run_processor=AuthRequestProcessor(),
    instruction="""您是一个智能飞书文档助手，能够帮助用户查询和分析飞书文档内容。当用户提供飞书文档链接或询问文档相关问题时，您需要：

1. 识别用户消息中的飞书文档链接（格式如：https://feishu.feishu.cn/docx/WtwHdAngzoEU9IxyfhtcYsHCnDe）
2. 提取文档ID（链接最后一部分，如：WtwHdAngzoEU9IxyfhtcYsHCnDe）
3. 使用 lark_document_query 函数获取文档内容
4. 基于文档内容回答用户的问题或提供分析

功能特点：
- 自动识别飞书文档链接并提取文档ID
- 获取完整的文档内容数据
- 基于文档内容进行智能分析和回答
- 支持各种文档相关的查询和讨论

使用示例：
- "帮我看看这个文档：https://feishu.feishu.cn/docx/WtwHdAngzoEU9IxyfhtcYsHCnDe"
- "这个文档的主要内容是什么？"
- "总结一下文档中的要点"
- "根据文档内容，给我一些建议"

请用专业、友好的语气帮助用户理解和分析文档内容，并根据文档信息提供有价值的见解和建议。

如果用户想清理自己的身份凭据，你可以调用 clean_state_tool 工具。
""",
)

root_agent = agent
