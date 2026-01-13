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


from agentkit.apps import AgentkitAgentServerApp
from veadk import Agent, Runner
from veadk.knowledgebase.knowledgebase import KnowledgeBase
from veadk.memory.short_term_memory import ShortTermMemory
import os

# 准备多个知识源
with open("/tmp/product_info.txt", "w") as f:
    f.write(
        "产品清单及价格：\n1. 高性能笔记本电脑 (Laptop Pro) - 价格：8999元\n   - 适用于专业设计和游戏，配备最新显卡。\n2. 智能手机 (SmartPhone X) - 价格：4999元\n   - 5G全网通，超长续航。\n3. 平板电脑 (Tablet Air) - 价格：2999元\n   - 轻薄便携，适合办公娱乐。"
    )
with open("/tmp/service_policy.txt", "w") as f:
    f.write(
        "售后服务政策：\n1. 质保期：所有电子产品提供1年免费质保。\n2. 退换货：购买后7天内无理由退货，15天内有质量问题换货。\n3. 客服支持：提供7x24小时在线客服咨询。"
    )

    # 创建知识库
kb = KnowledgeBase(
    backend="viking",
    app_name=os.getenv("DATABASE_VIKING_COLLECTION", "agentkit_knowledge_app"),
)
kb.add_from_files(
    files=["/tmp/product_info.txt", "/tmp/service_policy.txt"],
    tos_bucket_name=os.environ.get("DATABASE_TOS_BUCKET"),
)

# 创建agent
root_agent = Agent(
    name="test_agent",
    knowledgebase=kb,
    instruction="你是一个乐于助人的客服助手。你可以查阅知识库来回答关于产品类目、价格以及售后服务的问题。请根据知识库的内容准确回答。",
)

# 运行
runner = Runner(
    agent=root_agent,
    app_name="test_app",
    user_id="test_user",
)

short_term_memory = ShortTermMemory(backend="local")

agent_server_app = AgentkitAgentServerApp(
    agent=root_agent,
    short_term_memory=short_term_memory,
)

if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
