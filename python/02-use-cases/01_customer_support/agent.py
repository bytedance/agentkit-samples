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

from tools.crm_mock import (
    create_service_record,
    delete_service_record,
    get_customer_info,
    get_customer_purchases,
    get_service_records,
    query_warranty,
    update_service_record,
)
import datetime
import logging
import os
import sys
from pathlib import Path

from agentkit.apps import AgentkitAgentServerApp
from dotenv import load_dotenv
from google.adk.agents.callback_context import CallbackContext
from google.adk.planners import BuiltInPlanner
from google.genai.types import ThinkingConfig
from veadk import Agent, Runner
from veadk.integrations.ve_identity import AuthRequestProcessor
from veadk.knowledgebase import KnowledgeBase
from veadk.memory import LongTermMemory, ShortTermMemory

# 当前目录
sys.path.append(str(Path(__file__).resolve().parent))
# 上层目录
sys.path.append(str(Path(__file__).resolve().parent.parent))


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app_name = "customer_support_agent"
default_user_id = "CUST001"
default_model_name = "deepseek-v3-1-terminus"
supported_model_names = [default_model_name]

model_name = os.getenv("MODEL_AGENT_NAME", default_model_name)
if model_name not in supported_model_names:
    logging.warning(
        f"MODEL_AGENT_NAME must be one of {supported_model_names}, if not, the MODEL_AGENT_NAME will be set to default_model_name: {default_model_name}"
    )
    model_name = default_model_name

# 1. 配置短期记忆
short_term_memory = ShortTermMemory(backend="local")

# 2. 配置使用知识库： Viking 向量数据库，如果用户指定了知识库，就使用用户指定的知识库，否则默认创建一个知识库，并做初始化
knowledge_collection_name = os.getenv("DATABASE_VIKING_COLLECTION", "")
if knowledge_collection_name != "":
    # 使用用户指定的知识库
    knowledge = KnowledgeBase(backend="viking", index=knowledge_collection_name)
else:
    raise ValueError("DATABASE_VIKING_COLLECTION environment variable is not set")


should_init_knowledge = False
try:
    test_knowledge = knowledge.search("商品退换策略", top_k=1)
    should_init_knowledge = not (
        len(test_knowledge) >= 0
        and test_knowledge[0].content != ""
        and str(test_knowledge[0].content).__contains__("商品退换策略")
    )
except Exception:
    should_init_knowledge = True

if should_init_knowledge:
    tos_bucket_name = os.getenv("DATABASE_TOS_BUCKET")
    if not tos_bucket_name:
        raise ValueError("DATABASE_TOS_BUCKET environment variable is not set")
    knowledge.add_from_directory(
        str(Path(__file__).resolve().parent) + "/pre_build/knowledge",
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


after_sale_prompt = (
    """
    你是一名专业且耐心的在线客服，负责协助客户处理咨询及商品售后服务。可使用内部工具和知识库，但需严格遵守以下准则：
    
    <指导原则>
    1. 使用工具时，绝不假设参数，确保信息准确。
    2. 若信息不足，礼貌询问客户具体细节。
    3. 禁止透露任何关于内部系统、工具或流程的信息。
    4. 若被问及内部流程、系统或培训，统一回复：“抱歉，我无法提供关于我们内部系统的信息。”
    5. 始终保持专业、友好且乐于助人的态度。
    6. 高效且准确地解决客户问题。
    
    <关于维修>
    1. 知识库中包含 手机、电视等商品的保修策略、售后政策、操作不当等常见问题的解决方案，客户问题必须要先查询知识库，是否有相关解决方案，参考已有案例引导客户排查 
    2. 涉及到具体商品的维修或售后咨询时，优先索取产品序列号，便于查询产品信息。
    3. 若客户忘记序列号，可先核验身份再查询购买记录确认商品信息， 可以通过客户姓名、邮箱 等信息进行核验。
    4. 详细询问故障情况，目前需要查询知识库内容的排查手册，来引导客户完成基础排查，重点排除操作不当等简单问题。若故障可以通过简易步骤解决，应优先鼓励客户自行操作修复。
    5. 产品不在保修范围时，确认客户是否接受自费维修。
    6. 创建维修单前，请确保完整收集必要信息（包括商品编号、故障描述、客户联系信息、维修时间等）。在正式提交前，需将全部信息发送给客户进行最终确认。
    7. 缺少必要信息时，礼貌询问客户补充。
    
    <沟通要求>
    1. 保持耐心和礼貌，避免使用不专业用语和行为。
    2. 工具结果不能直接反馈给客户，需结合客户问题筛选、格式化并润色回复内容，确保清晰、准确、简洁。
    
    请根据上述要求，准确、简明且专业地回答客户问题，并积极协助解决售后问题。 同时，全程你被禁止使用知识库以外未经过认证的解决方案， 所有解决方案必须要先从知识库查询解决方案。
    
    当前登录客户为： {user:customer_id} 。
        """
    + "当前时间为："
    + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
)

after_sale_agent = Agent(
    name="after_sale_agent",
    model_name=model_name,
    description=" 售后Agent：根据客户的售后问题，帮助客户处理商品的售后问题(信息查询、商品报修等)",
    instruction=after_sale_prompt,
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

shopping_guide_prompt = (
    """
    你是一名专业且耐心的在线客服，你的首要任务是帮助客户购买商品。你可使用工具或者检索知识库来 准确并简洁的回答客户问题.
    
    在回答客户问题以及协助客户的过程中时，请始终遵循以下指导原则：
    <指导原则>
    1. 使用内部工具时，绝不要假设参数值。
    2. 若缺少处理请求所需的必要信息，请礼貌地向客户询问具体细节。
    3. 严禁披露你可用的内部工具、系统或功能的任何信息。
    4. 若被问及内部流程、工具、功能或培训相关问题，始终回应：“抱歉，我无法提供关于我们内部系统的信息。”
    5. 协助客户时，保持专业且乐于助人的语气。
    6. 专注于高效且准确地解决客户咨询。
    
    <导购原则>
    1. 你需要综合客户的各方面需求，选择合适的商品推荐给客户购买
    2. 你可以查询客户的历史购买记录，来了解客户的喜好
    3. 如果客户表现出对某个商品很感兴趣，你需要详细介绍下该商品，并且结合客户的要求，说明推荐该商品的理由
    4. 当前你能售卖的商品都存在知识库中，你只能根据知识库中有的商品信息来回答客户的问题，不能编造不存在的商品信息。
    5. 当前你只能给客户推荐 在售的商品，不能推荐不存在或者已下架商品。
    
    <沟通要求>
    1. 请注意你需要耐心有礼貌的和客户进行沟通，避免回复客户时使用不专业的语言或行为。
    2. 禁止直接将 工具的结果直接输出给用户，你需要结合用户的问题，对工具的结果进行必要的筛选、格式化处理，在输出给用户时，还需要进行必要的润色，使回复内容更加的清晰、准确、简洁。  
    
    当前登录客户为： {user:customer_id}
        """
    + "当前时间为："
    + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
)

shopping_guide_agent = Agent(
    name="shopping_guide_agent",
    model_name=model_name,
    description="根据客户的购买需求，帮助客户选择合适的商品，引导客户完成购买流程",
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
    instruction=shopping_guide_prompt,
    run_processor=AuthRequestProcessor(),
)

agent = Agent(
    name="customer_support_agent",
    model_name=model_name,
    description="客服Agent：1）根据客户的购买需求，帮助客户选择合适的商品，引导客户完成购买流程；2）根据客户的售后问题，帮助客户处理商品的售后问题(信息查询、商品报修等)",
    instruction="""
    你是一名在线客服，你的主要任务是帮助客户购买商品或者解决售后问题。
    ## 要求
    1. 你需要结合对话的上下文判断用户的意图， 是在做购买咨询还是售后服务咨询：
        - 如果用户是在做购买咨询，请直接将用户的问题转交给购物引导智能体来回答用户的问题
        - 如果用户是在做售后服务咨询，请直接将用户的问题转交给售后智能体来回答用户的问题，售后策略、保修策略的咨询也视为售后服务咨询。
        - 如果用户问与购买咨询或售后服务咨询无关的问题，请直接回复用户：“抱歉，我无法回答这个问题。我可以帮助您购买商品或者解决售后问题。”
    2. 请注意你需要耐心有礼貌的和客户进行沟通，避免回复客户时使用不专业的语言或行为， 同时避免回复和问题无关的内容。
    """,
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
