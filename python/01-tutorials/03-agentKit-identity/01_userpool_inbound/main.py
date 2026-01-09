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
实验1: 使用用户池配置用户身份 (Inbound 认证)

本示例展示如何为智能体配置 Inbound 认证，确保只有授权用户才能访问。

运行方式:
    uv run veadk web

访问地址:
    http://127.0.0.1:8000

认证流程:
    1. 用户访问应用 → 自动跳转登录页
    2. 用户输入凭证 → 用户池验证身份
    3. 验证通过 → 返回 JWT Token
    4. 携带 Token 访问 Agent → 允许调用
"""

from veadk import Agent, Runner
from veadk.memory.short_term_memory import ShortTermMemory

# ============================================================
# Agent 配置
# ============================================================

APP_NAME = "secure_agent_demo"

agent = Agent(
    name="secure_assistant",
    description="一个安全的智能助手，只有授权用户才能访问",
    instruction="""你是一个企业级智能助手，专门为已授权的用户提供服务。

你的职责：
1. 回答用户的问题
2. 提供专业的建议
3. 协助完成日常工作任务

注意事项：
- 你只会为通过身份验证的用户提供服务
- 所有对话都会被记录用于审计
- 请遵循企业安全政策
""",
)

# 创建 Runner，启用短期记忆
runner = Runner(
    agent=agent,
    short_term_memory=ShortTermMemory(backend="local"),
    app_name=APP_NAME,
)

# ============================================================
# 导出 root_agent 供 veadk web 使用
# ============================================================

root_agent = agent


# ============================================================
# 本地测试入口（可选）
# ============================================================


async def test_agent():
    """本地测试函数（绕过认证，仅用于开发调试）"""
    response = await runner.run(
        messages="你好，请介绍一下你自己",
        user_id="test_user",
        session_id="test_session",
    )
    print(f"Agent 响应: {response}")


if __name__ == "__main__":
    import asyncio

    print("=" * 60)
    print("教程1: Inbound 认证示例")
    print("=" * 60)
    print()
    print("正式运行请使用: uv run veadk web")
    print("这将启动带有 OAuth2 认证的 Web 服务")
    print()
    print("以下为本地测试模式（无认证）：")
    print("-" * 60)

    asyncio.run(test_agent())
