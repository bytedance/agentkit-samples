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

import asyncio

from veadk import Agent, Runner
from veadk.memory import LongTermMemory, ShortTermMemory

vikingmem_app_name = "ltm_local"
app_name = "test_app"
user_id = "test_user"
history_session_id = "history_session"  # 短期记忆会话ID
new_session_id = "new_session"  # 新会话ID（无短期记忆）

# 短期记忆：仅同session有效
agent1 = Agent(name="test_agent", instruction="You are a helpful assistant.")

runner1 = Runner(
    agent=agent1,
    short_term_memory=ShortTermMemory(),
    app_name=app_name,
    user_id=user_id,
)


async def main():
    # 存入短期记忆
    response1 = await runner1.run(
        messages="My habby is 0xabcd", session_id=history_session_id
    )
    print(f"Response 1: {response1}\n")

    # 同session读取短期记忆
    response2 = await runner1.run(
        messages="What is my habby?", session_id=history_session_id
    )
    print(f"Response 2: {response2}\n")

    # 新session无短期记忆（失败）
    response3 = await runner1.run(
        messages="What is my habby?", session_id=new_session_id
    )
    print(f"Response 3: {response3}\n")

    # 初始化长期记忆（Viking后端）
    long_term_memory = LongTermMemory(backend="viking", index=vikingmem_app_name)
    agent1.long_term_memory = long_term_memory
    runner1.agent = agent1
    await runner1.save_session_to_long_term_memory(
        session_id=history_session_id
    )  # 短期转长期记忆

    # 长期记忆：跨session有效
    agent2 = Agent(
        name="test_agent",
        instruction="Use LoadMemory tool to search previous info.",
        long_term_memory=long_term_memory,
    )
    runner2 = Runner(agent=agent2, app_name=app_name, user_id=user_id)

    # 新session读取长期记忆
    response4 = await runner2.run(
        messages="What is my habby?", session_id=new_session_id
    )
    print(f"Response 4: {response4}")


if __name__ == "__main__":
    asyncio.run(main())
