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
实验2: 飞书 IdP 联合登录

本示例展示如何使用飞书作为外部身份提供商(IdP)进行联合登录。
与实验1的区别在于：用户使用飞书账号登录，而不是用户池本地账号。

核心特性:
    - 飞书账号一键登录: 无需创建本地账号
    - 企业身份集成: 利用飞书的企业通讯录
    - 单点登录(SSO): 已登录飞书则无需再次认证

运行方式:
    uv run veadk web

访问地址:
    http://127.0.0.1:8000

认证流程:
    1. 用户访问应用 → 显示登录页
    2. 点击"使用飞书登录" → 跳转飞书授权页
    3. 用户在飞书确认授权 → 返回应用
    4. 应用获取飞书用户信息 → 创建/关联本地会话
    5. 用户成功访问 Agent
"""

from veadk import Agent, Runner
from veadk.memory.short_term_memory import ShortTermMemory

# ============================================================
# Agent 配置
# ============================================================

APP_NAME = "feishu_sso_agent_demo"

agent = Agent(
    name="feishu_sso_assistant",
    description="一个支持飞书单点登录的智能助手",
    instruction="""你是一个企业级智能助手，专门为通过飞书账号登录的用户提供服务。

你的职责：
1. 回答用户的问题
2. 提供专业的建议
3. 协助完成日常工作任务

身份认证说明：
- 你只会为通过飞书账号验证的用户提供服务
- 用户的飞书身份信息可用于个性化服务
- 所有对话都会被记录用于审计

企业场景支持：
- 可以识别用户的飞书组织身份
- 支持与飞书工作流集成
- 遵循企业安全政策
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
        messages="你好，我是通过飞书登录的用户，请介绍一下你自己",
        user_id="feishu_test_user",
        session_id="test_session",
    )
    print(f"Agent 响应: {response}")


if __name__ == "__main__":
    import asyncio

    print("=" * 60)
    print("实验2: 飞书 IdP 联合登录示例")
    print("=" * 60)
    print()
    print("正式运行请使用: uv run veadk web")
    print("这将启动带有飞书 SSO 认证的 Web 服务")
    print()
    print("登录流程:")
    print("1. 访问 http://127.0.0.1:8000")
    print("2. 在登录页点击 '使用飞书登录'")
    print("3. 在飞书授权页面点击 '授权'")
    print("4. 返回应用后点击 '允许访问'")
    print("5. 成功登录，开始与 Agent 对话")
    print()
    print("-" * 60)
    print("以下为本地测试模式（无认证）：")
    print("-" * 60)

    asyncio.run(test_agent())
