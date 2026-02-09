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

import datetime
import logging
import os
import sys
from pathlib import Path
from veadk.configs.database_configs import NormalTOSConfig

# 当前目录
sys.path.append(str(Path(__file__).resolve().parent))

from tools.crm_mock import (
    create_service_record,
    delete_service_record,
    get_customer_info,
    get_customer_purchases,
    get_service_records,
    query_warranty,
    update_service_record,
)

from agentkit.apps import AgentkitAgentServerApp
from dotenv import load_dotenv
from google.adk.agents.callback_context import CallbackContext
from google.adk.planners import BuiltInPlanner
from google.genai.types import ThinkingConfig
from veadk import Agent, Runner
from veadk.integrations.ve_identity import AuthRequestProcessor
from veadk.knowledgebase import KnowledgeBase
from veadk.memory import LongTermMemory, ShortTermMemory
from prompts.prompt import (
    AFTER_SALE_PROMPT_CN,
    AFTER_SALE_PROMPT_EN,
    SHOPPING_GUIDE_PROMPT_CN,
    SHOPPING_GUIDE_PROMPT_EN,
    ROOT_AGENT_INSTRUCTION_CN,
    ROOT_AGENT_INSTRUCTION_EN,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app_name = "customer_support_agent"
default_user_id = "CUST001"

# 默认模型设置
default_model_name = "deepseek-v3-2-251201"

model_name = os.getenv("MODEL_AGENT_NAME", default_model_name)

# 根据 CLOUD_PROVIDER 环境变量选择语言
provider = os.getenv("CLOUD_PROVIDER")
if provider and provider.lower() == "byteplus":
    AFTER_SALE_PROMPT = AFTER_SALE_PROMPT_EN
    SHOPPING_GUIDE_PROMPT = SHOPPING_GUIDE_PROMPT_EN
    ROOT_AGENT_INSTRUCTION = ROOT_AGENT_INSTRUCTION_EN
    AFTER_SALE_DESCRIPTION = "After-Sales Agent: handles after-sales inquiries such as information lookup and repair requests."
    SHOPPING_GUIDE_DESCRIPTION = "Shopping Guide Agent: helps customers choose suitable products and guides them through the purchase flow."
    ROOT_AGENT_DESCRIPTION = (
        "Customer Support Agent: 1) guides customers on product selection and purchase; "
        "2) handles after-sales issues such as information lookup and repair requests."
    )
    knowledge_directory = "pre_build/knowledge_en"
    knowledge_probe = "Return & Exchange Policy"
else:
    AFTER_SALE_PROMPT = AFTER_SALE_PROMPT_CN
    SHOPPING_GUIDE_PROMPT = SHOPPING_GUIDE_PROMPT_CN
    ROOT_AGENT_INSTRUCTION = ROOT_AGENT_INSTRUCTION_CN
    AFTER_SALE_DESCRIPTION = "售后Agent：根据客户的售后问题，帮助客户处理商品的售后问题（信息查询、商品报修等）。"
    SHOPPING_GUIDE_DESCRIPTION = (
        "导购Agent：根据客户的购买需求，帮助客户选择合适的商品，引导客户完成购买流程。"
    )
    ROOT_AGENT_DESCRIPTION = (
        "客服Agent：1）根据客户的购买需求，帮助客户选择合适的商品，引导客户完成购买流程；"
        "2）根据客户的售后问题，帮助客户处理商品的售后问题（信息查询、商品报修等）。"
    )
    knowledge_directory = "pre_build/knowledge"
    knowledge_probe = "商品退换策略"

# 1. 配置短期记忆
short_term_memory = ShortTermMemory(backend="local")

# 2. 配置使用知识库： Viking 向量数据库，如果用户指定了知识库，就使用用户指定的知识库，否则默认创建一个知识库，并做初始化
knowledge_collection_name = os.getenv("DATABASE_VIKING_COLLECTION", "")
if knowledge_collection_name != "":
    # 使用用户指定的知识库
    if provider and provider.lower() == "byteplus":
        knowledge = KnowledgeBase(
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
        knowledge = KnowledgeBase(backend="viking", index=knowledge_collection_name)
else:
    raise ValueError("DATABASE_VIKING_COLLECTION environment variable is not set")


should_init_knowledge = False
try:
    test_knowledge = knowledge.search(knowledge_probe, top_k=1)
    should_init_knowledge = not (
        len(test_knowledge) >= 0
        and test_knowledge[0].content != ""
        and str(test_knowledge[0].content).__contains__(knowledge_probe)
    )
except Exception:
    should_init_knowledge = True

if should_init_knowledge:
    tos_bucket_name = os.getenv("DATABASE_TOS_BUCKET")
    if not tos_bucket_name:
        raise ValueError("DATABASE_TOS_BUCKET environment variable is not set")
    knowledge.add_from_directory(
        str(Path(__file__).resolve().parent) + f"/{knowledge_directory}",
        tos_bucket_name=tos_bucket_name,
    )

# 3. 配置长期记忆: 如果配置了Mem0，就使用Mem0，否则使用Viking，都不配置，默认创建一个Viking记忆库
use_mem0 = os.getenv("DATABASE_MEM0_BASE_URL") and os.getenv("DATABASE_MEM0_API_KEY")
if use_mem0:
    long_term_memory = LongTermMemory(backend="mem0", top_k=3, app_name=app_name)
else:
    use_viking_mem = os.getenv("DATABASE_VIKINGMEM_COLLECTION") and os.getenv(
        "DATABASE_VIKINGMEM_MEMORY_TYPE"
    )
    if use_viking_mem:
        long_term_memory = LongTermMemory(
            backend="viking", index=os.getenv("DATABASE_VIKINGMEM_COLLECTION")
        )
    else:
        raise ValueError(
            "DATABASE_VIKINGMEM_COLLECTION or DATABASE_MEM0_BASE_URL variable is not set"
        )

# 4. 导入crm 系统的函数工具
crm_tool = [
    create_service_record,
    update_service_record,
    delete_service_record,
    get_customer_info,
    get_customer_purchases,
    get_service_records,
    query_warranty,
]


# 5. 通过前置拦截器，在智能体执行前，设置默认的customer_id
def before_agent_execution(callback_context: CallbackContext):
    # user_id = callback_context._invocation_context.user_id
    callback_context.state["user:customer_id"] = default_user_id


# 这里仅做记忆保存的演示，实际根据需求选择会话保存到长期记忆中
async def after_agent_execution(callback_context: CallbackContext):
    session = callback_context._invocation_context.session
    await long_term_memory.add_session_to_memory(session)


after_sale_agent = Agent(
    name="after_sale_agent",
    model_name=model_name,
    description=AFTER_SALE_DESCRIPTION,
    instruction=AFTER_SALE_PROMPT
    + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    planner=BuiltInPlanner(
        thinking_config=ThinkingConfig(
            include_thoughts=True,
            thinking_budget=1024,
        )
    ),
    knowledgebase=knowledge,
    long_term_memory=long_term_memory,
    tools=crm_tool,
    before_agent_callback=before_agent_execution,
    after_agent_callback=after_agent_execution,
    run_processor=AuthRequestProcessor(),
)


shopping_guide_agent = Agent(
    name="shopping_guide_agent",
    model_name=model_name,
    description=SHOPPING_GUIDE_DESCRIPTION,
    planner=BuiltInPlanner(
        thinking_config=ThinkingConfig(
            include_thoughts=True,
            thinking_budget=1024,
        )
    ),
    knowledgebase=knowledge,
    long_term_memory=long_term_memory,
    tools=[get_customer_info, get_customer_purchases],
    before_agent_callback=before_agent_execution,
    after_agent_callback=after_agent_execution,
    instruction=SHOPPING_GUIDE_PROMPT
    + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    run_processor=AuthRequestProcessor(),
)

agent = Agent(
    name="customer_support_agent",
    model_name=model_name,
    description=ROOT_AGENT_DESCRIPTION,
    instruction=ROOT_AGENT_INSTRUCTION,
    sub_agents=[after_sale_agent, shopping_guide_agent],
    long_term_memory=long_term_memory,
    after_agent_callback=after_agent_execution,
)

runner = Runner(agent=agent, app_name=app_name)
root_agent = agent

agent_server_app = AgentkitAgentServerApp(
    agent=root_agent, short_term_memory=short_term_memory
)

if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
