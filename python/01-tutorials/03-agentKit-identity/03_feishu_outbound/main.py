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
实验3 (进阶): 以 GitHub 为例，安全访问外部工具 (Outbound 凭证托管)

本示例展示如何使用 Agent Identity 的凭证托管功能，
让智能体安全无感地访问 GitHub API。

核心特性:
    - 凭证不落地: OAuth Token 由平台统一管理
    - 用户级隔离: 每个用户的 GitHub 授权独立
    - OAuth 自动化: 首次使用引导授权，后续无感

本地运行方式:
    1. 设置环境变量 RUNTIME_IAM_ROLE_TRN 指向具备 IDReadOnly 权限的 role
    2. uv run veadk web
    3. 访问 http://127.0.0.1:8000

测试指令:
    - "查询我的 GitHub 用户信息"
    - "列出我的 GitHub 仓库"
    - "清理我的身份凭据" (重新触发授权)
"""

# ============================================================
# Monkey patch: 修复 veadk 0.2.22 的 RuntimeError bug
# ============================================================
import sys


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

# ============================================================
# 正常的导入和代码
# ============================================================

import json
import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from veadk import Agent
from veadk.integrations.ve_identity import (
    AuthRequestProcessor,
    VeIdentityFunctionTool,
    oauth2_auth,
)
from veadk.integrations.ve_identity.auth_mixins import OAuth2AuthMixin
from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.tool_context import ToolContext

# 从环境变量读取凭证提供者名称
GITHUB_CREDENTIAL_PROVIDER = os.getenv("GITHUB_CREDENTIAL_PROVIDER", "github_oauth")
FEISHU_CREDENTIAL_PROVIDER = os.getenv("FEISHU_CREDENTIAL_PROVIDER", "feishu_oauth")

print(f"[CONFIG] GITHUB_CREDENTIAL_PROVIDER={GITHUB_CREDENTIAL_PROVIDER}")
print(f"[CONFIG] FEISHU_CREDENTIAL_PROVIDER={FEISHU_CREDENTIAL_PROVIDER}")

# ============================================================
# GitHub API 工具
# ============================================================


async def github_get_user(*, access_token: str) -> str:
    """
    获取当前用户的 GitHub 信息

    Args:
        access_token: GitHub OAuth access_token（由凭证托管自动注入）

    Returns:
        用户信息的 JSON 字符串
    """
    try:
        print(f"[GitHub] 获取用户信息, Token: {access_token[:8]}...")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )

            if response.status_code != 200:
                return f"GitHub API 错误: {response.status_code} - {response.text}"

            user_data = response.json()
            return json.dumps(
                {
                    "login": user_data.get("login"),
                    "name": user_data.get("name"),
                    "email": user_data.get("email"),
                    "bio": user_data.get("bio"),
                    "public_repos": user_data.get("public_repos"),
                    "followers": user_data.get("followers"),
                    "following": user_data.get("following"),
                    "created_at": user_data.get("created_at"),
                    "html_url": user_data.get("html_url"),
                },
                indent=2,
                ensure_ascii=False,
            )

    except Exception as e:
        return f"获取用户信息出错: {str(e)}"


async def github_list_repos(*, access_token: str) -> str:
    """
    列出当前用户的 GitHub 仓库

    Args:
        access_token: GitHub OAuth access_token（由凭证托管自动注入）

    Returns:
        仓库列表的 JSON 字符串
    """
    try:
        print(f"[GitHub] 列出仓库, Token: {access_token[:8]}...")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.github.com/user/repos",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                params={
                    "sort": "updated",
                    "per_page": 10,
                },
            )

            if response.status_code != 200:
                return f"GitHub API 错误: {response.status_code} - {response.text}"

            repos = response.json()
            result = []
            for repo in repos:
                result.append(
                    {
                        "name": repo.get("name"),
                        "full_name": repo.get("full_name"),
                        "description": repo.get("description"),
                        "private": repo.get("private"),
                        "html_url": repo.get("html_url"),
                        "language": repo.get("language"),
                        "stargazers_count": repo.get("stargazers_count"),
                        "updated_at": repo.get("updated_at"),
                    }
                )

            return json.dumps(result, indent=2, ensure_ascii=False)

    except Exception as e:
        return f"列出仓库出错: {str(e)}"


async def github_get_repo(owner: str, repo: str, *, access_token: str) -> str:
    """
    获取指定 GitHub 仓库的详细信息

    Args:
        owner: 仓库所有者
        repo: 仓库名称
        access_token: GitHub OAuth access_token（由凭证托管自动注入）

    Returns:
        仓库详情的 JSON 字符串
    """
    try:
        print(f"[GitHub] 获取仓库 {owner}/{repo}, Token: {access_token[:8]}...")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )

            if response.status_code != 200:
                return f"GitHub API 错误: {response.status_code} - {response.text}"

            repo_data = response.json()
            return json.dumps(
                {
                    "name": repo_data.get("name"),
                    "full_name": repo_data.get("full_name"),
                    "description": repo_data.get("description"),
                    "private": repo_data.get("private"),
                    "html_url": repo_data.get("html_url"),
                    "language": repo_data.get("language"),
                    "stargazers_count": repo_data.get("stargazers_count"),
                    "forks_count": repo_data.get("forks_count"),
                    "open_issues_count": repo_data.get("open_issues_count"),
                    "default_branch": repo_data.get("default_branch"),
                    "created_at": repo_data.get("created_at"),
                    "updated_at": repo_data.get("updated_at"),
                    "topics": repo_data.get("topics", []),
                },
                indent=2,
                ensure_ascii=False,
            )

    except Exception as e:
        return f"获取仓库信息出错: {str(e)}"


# 使用凭证托管包装 GitHub 工具
github_user_tool = VeIdentityFunctionTool(
    func=github_get_user,
    auth_config=oauth2_auth(
        provider_name=GITHUB_CREDENTIAL_PROVIDER,
        auth_flow="USER_FEDERATION",
    ),
)

github_repos_tool = VeIdentityFunctionTool(
    func=github_list_repos,
    auth_config=oauth2_auth(
        provider_name=GITHUB_CREDENTIAL_PROVIDER,
        auth_flow="USER_FEDERATION",
    ),
)

github_repo_detail_tool = VeIdentityFunctionTool(
    func=github_get_repo,
    auth_config=oauth2_auth(
        provider_name=GITHUB_CREDENTIAL_PROVIDER,
        auth_flow="USER_FEDERATION",
    ),
)


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


async def feishu_list_docs(*, access_token: str) -> str:
    """
    列出用户最近访问的飞书文档

    Args:
        access_token: 飞书 OAuth access_token（由凭证托管自动注入）

    Returns:
        最近文档列表
    """
    try:
        print(f"[飞书] 列出最近文档, Token: {access_token[:8]}...")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://open.feishu.cn/open-apis/drive/v1/files",
                headers={
                    "Authorization": f"Bearer {access_token}",
                },
                params={
                    "page_size": 10,
                    "order_by": "EditedTime",
                    "direction": "DESC",
                    "file_type": "docx",
                },
            )

            if response.status_code != 200:
                error_data = response.json()
                return f"飞书 API 错误: {response.status_code} - {error_data.get('msg', response.text)}"

            data = response.json()
            if data.get("code") != 0:
                return f"飞书 API 错误: {data.get('code')} - {data.get('msg')}"

            files = data.get("data", {}).get("files", [])
            result = []
            for f in files:
                result.append(
                    {
                        "name": f.get("name"),
                        "token": f.get("token"),
                        "type": f.get("type"),
                        "url": f.get("url"),
                        "created_time": f.get("created_time"),
                        "modified_time": f.get("modified_time"),
                    }
                )

            return json.dumps(result, indent=2, ensure_ascii=False)

    except Exception as e:
        return f"列出飞书文档出错: {str(e)}"


# 使用凭证托管包装飞书工具
feishu_doc_tool = VeIdentityFunctionTool(
    func=feishu_get_document,
    auth_config=oauth2_auth(
        provider_name=FEISHU_CREDENTIAL_PROVIDER,
        auth_flow="USER_FEDERATION",
    ),
)

feishu_list_tool = VeIdentityFunctionTool(
    func=feishu_list_docs,
    auth_config=oauth2_auth(
        provider_name=FEISHU_CREDENTIAL_PROVIDER,
        auth_flow="USER_FEDERATION",
    ),
)


# ============================================================
# 凭证清理工具（用于重新触发授权）
# ============================================================


async def clean_github_state(
    args: dict[str, Any], *, tool_context: ToolContext
) -> None:
    """
    清理用户的 GitHub OAuth 身份凭据

    用户可以通过说"重新授权 GitHub"来重新触发 GitHub 授权流程。
    """
    oauth_client = OAuth2AuthMixin(
        provider_name=GITHUB_CREDENTIAL_PROVIDER,
        auth_flow="USER_FEDERATION",
        force_authentication=True,
    )
    await oauth_client._get_oauth2_token_or_auth_url(tool_context=tool_context)
    return None


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


clean_github_tool = FunctionTool(clean_github_state)
clean_feishu_tool = FunctionTool(clean_feishu_state)


# ============================================================
# Agent 定义
# ============================================================

agent: Agent = Agent(
    name="github_assistant",
    tools=[
        # GitHub 工具
        github_user_tool,
        github_repos_tool,
        github_repo_detail_tool,
        # 飞书工具
        feishu_doc_tool,
        feishu_list_tool,
        # 凭证清理工具
        clean_github_tool,
        clean_feishu_tool,
    ],
    run_processor=AuthRequestProcessor(),
    tracers=[],
    instruction="""您是一个多平台助手，能够帮助用户访问 GitHub 和飞书的资源。

## GitHub 功能
1. **获取用户信息** - 使用 github_get_user 获取当前用户的 GitHub 个人资料
2. **列出仓库** - 使用 github_list_repos 列出用户的仓库
3. **查看仓库详情** - 使用 github_get_repo 获取指定仓库的详细信息

## 飞书功能
1. **获取文档内容** - 使用 feishu_get_document 获取飞书文档内容（需要文档 ID）
2. **列出最近文档** - 使用 feishu_list_docs 列出用户最近访问的飞书文档

## 使用示例
- "查询我的 GitHub 用户信息"
- "列出我的 GitHub 仓库"
- "查看 volcengine/agentkit-samples 仓库的信息"
- "帮我总结这个飞书文档: ABC123"
- "列出我最近的飞书文档"

## 重新授权
- 说"重新授权 GitHub"可以重新触发 GitHub 授权
- 说"重新授权飞书"可以重新触发飞书授权
""",
)

root_agent = agent


# ============================================================
# 本地运行说明
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("教程3 (进阶): GitHub Outbound 凭证托管示例")
    print("=" * 60)
    print()
    print("本地运行方式:")
    print("  1. 确保 .env 中配置了 RUNTIME_IAM_ROLE_TRN")
    print("  2. uv run veadk web")
    print("  3. 访问 http://127.0.0.1:8000")
    print()
    print("测试指令:")
    print("- 查询我的 GitHub 用户信息")
    print("- 列出我的仓库")
    print("- 查看 owner/repo 仓库的信息")
    print()
    print("清理凭证: 发送 '清理我的身份凭据'")
