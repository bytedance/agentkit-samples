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


import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))

from agentkit.apps import AgentkitAgentServerApp
from veadk import Agent, Runner
from veadk.knowledgebase.knowledgebase import KnowledgeBase
from veadk.memory.short_term_memory import ShortTermMemory
from prompts.prompt import ROOT_AGENT_INSTRUCTION_CN, ROOT_AGENT_INSTRUCTION_EN
from veadk.configs.database_configs import NormalTOSConfig

provider = os.getenv("CLOUD_PROVIDER")
if provider and provider.lower() == "byteplus":
    ROOT_AGENT_INSTRUCTION = ROOT_AGENT_INSTRUCTION_EN

# prepare multiple knowledge sources
with open("/tmp/product_info.txt", "w") as f:
    if provider and provider.lower() == "byteplus":
        f.write(
            "Product List and Prices: \n1. High-Performance Laptop (Laptop Pro) - Price: 8999 RMB\n - Suitable for professional design and gaming, equipped with the latest graphics card. \n2. Smartphone (SmartPhone X) - Price: 4999 RMB\n - 5G full network compatibility, ultra-long battery life. \n3. Tablet (Tablet Air) - Price: 2999 RMB\n - Lightweight and portable, suitable for office work and entertainment."
        )
    else:
        f.write(
            "产品清单及价格：\n1. 高性能笔记本电脑 (Laptop Pro) - 价格：8999元\n   - 适用于专业设计和游戏，配备最新显卡。\n2. 智能手机 (SmartPhone X) - 价格：4999元\n   - 5G全网通，超长续航。\n3. 平板电脑 (Tablet Air) - 价格：2999元\n   - 轻薄便携，适合办公娱乐。"
        )

with open("/tmp/service_policy.txt", "w") as f:
    if provider and provider.lower() == "byteplus":
        f.write(
            "After-sales service policy: \n1. Warranty period: All electronic products come with a 1-year free warranty. \n2. Returns and exchanges: Returns are accepted within 7 days of purchase for any reason; exchanges are available within 15 days for quality issues. \n3. Customer support: 24/7 online customer service is available."
        )
    else:
        f.write(
            "售后服务政策：\n1. 质保期：所有电子产品提供1年免费质保。\n2. 退换货：购买后7天内无理由退货，15天内有质量问题换货。\n3. 客服支持：提供7x24小时在线客服咨询。"
        )

# create knowledge base
knowledge_collection_name = os.getenv("DATABASE_VIKING_COLLECTION", "")
if knowledge_collection_name != "":
    # use user specified knowledge base
    if provider and provider.lower() == "byteplus":
        kb = KnowledgeBase(
            backend="viking",
            backend_config={
                "index": knowledge_collection_name,
                "tos_config": NormalTOSConfig(
                    bucket=os.getenv("DATABASE_TOS_BUCKET"),
                    region=os.getenv("DATABASE_TOS_REGION", "cn-hongkong"),
                    endpoint=os.getenv(
                        "DATABASE_TOS_ENDPOINT", "tos-cn-hongkong.bytepluses.com"
                    ),
                ),
            },
        )
    else:
        kb = KnowledgeBase(backend="viking", index=knowledge_collection_name)
else:
    raise ValueError("DATABASE_VIKING_COLLECTION environment variable is not set")

kb.add_from_files(
    files=["/tmp/product_info.txt", "/tmp/service_policy.txt"],
    tos_bucket_name=os.environ.get("DATABASE_TOS_BUCKET"),
)

ROOT_AGENT_INSTRUCTION = ROOT_AGENT_INSTRUCTION_CN

# create agent
root_agent = Agent(
    name="vikingdb_agent",
    model_name=os.getenv("MODEL_AGENT_NAME", "deepseek-v3-2-251201"),
    knowledgebase=kb,
    instruction=ROOT_AGENT_INSTRUCTION,
)

# run agent
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
