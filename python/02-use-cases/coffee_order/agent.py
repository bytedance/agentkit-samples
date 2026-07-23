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
import logging
import os
import sys
from pathlib import Path

from agentkit.apps import AgentkitAgentServerApp
from veadk import Agent
from veadk.knowledgebase import KnowledgeBase
from veadk.memory import LongTermMemory, ShortTermMemory

# add current dir path to Python module search path
sys.path.append(str(Path(__file__).resolve().parent))
# add parent dir path to Python module search path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from mock_pay_service import create_order, create_order_number

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app_name = "online_order_agent"
# support users to update model in runtime environment variable
model_name = os.getenv("MODEL_AGENT_NAME", "deepseek-v3-2-251201")

#  config knowledgebase backend: Viking vector database
knowledge_collection_name = os.getenv("DATABASE_VIKING_COLLECTION", "")
if knowledge_collection_name != "":
    # use user specified knowledge base
    knowledge = KnowledgeBase(backend="viking", index=knowledge_collection_name)
else:
    raise ValueError("DATABASE_VIKING_COLLECTION environment variable is not set")

should_init_knowledge = False
try:
    test_knowledge = knowledge.search("拿铁咖啡", top_k=1)
    should_init_knowledge = not (
        len(test_knowledge) >= 0
        and test_knowledge[0].content != ""
        and str(test_knowledge[0].content).__contains__("拿铁咖啡")
    )
except Exception:
    should_init_knowledge = True

if should_init_knowledge:
    # depend on tos bucket to upload knowledgebase content
    tos_bucket_name = os.getenv("DATABASE_TOS_BUCKET", "")
    tos_region = os.getenv("DATABASE_TOS_REGION", "")
    if tos_bucket_name == "" or tos_region == "":
        raise ValueError(
            "DATABASE_TOS_BUCKET or DATABASE_TOS_REGION environment variable is not set"
        )

    # add files in the directory to knowledgebase backend.
    try:
        success = knowledge.add_from_directory(
            str(Path(__file__).resolve().parent) + "/knowledge",
            tos_bucket_name=tos_bucket_name,
            tos_region=tos_region,
        )
        if not success:
            raise RuntimeError("Failed to add files to knowledge base")
        logger.info(
            f"Successfully added files to knowledge base index {knowledge_collection_name} or {app_name}"
        )
    except Exception as e:
        logger.error(f"Error adding files to knowledge base: {e}")
        raise e

# config long term memory backend: support Viking vector database or Mem0
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

# config short term memory backend: local memory
short_term_memory = ShortTermMemory(backend="local")

prompt = """
# 智能咖啡/甜品点单机器人系统提示

你是一个专业的线上咖啡/甜品点单智能机器人，负责处理用户的咖啡/甜品点单需求，核心功能包括信息检索、订单生成、工具调用及结果反馈。请严格遵循以下流程与规则：

## 核心职责
1. **需求解析**：精准理解用户的咖啡/甜品点单请求，提取关键信息（咖啡名称、类型、温度、杯型，甜度、数量）
2. **用户点单历史检索**：根据用户ID，从长期记忆中检索（load_memory工具）用户的历史点单记录，分析用户偏好，给出对应产品推荐
3. **咖啡推荐**：基于用户需求，推荐合适的咖啡名称及配置选项
4. **知识检索**：根据用户需求，从咖啡/甜品知识库中匹配对应的商品信息（参考字段：名称、类型、温度、杯型、价格、甜度）
5. **订单生成**：基于检索结果和用户定制需求，生成规范的订单内容
6. **工具调用**：使用指定格式调用payservice工具完成下单，获取支付链接
7. **结果反馈**：将支付链接payment_url展示给用户，并提供必要的订单信息核对
8. **搭配甜品推荐**：根据用户点单的咖啡类型，推荐合适的甜品搭配（如蛋糕、饼干等），推荐用户购买，提升用户体验和客单价。


## 处理流程
1. **信息确认**：若用户需求不明确（如未指定咖啡名称、可选项缺失等），需友好追问补充关键信息（例："请问您需要热饮还是冰饮呢？"）
2. **历史偏好分析**：调用load_memory工具，检索用户历史点单记录，分析偏好，若有相关记录，可进行推荐（例："根据您之前的选择，您可能会喜欢我们的焦糖玛奇朵，您需要尝试一下吗？"）
3. **知识库匹配**：严格依据知识库信息进行匹配，若检索不到对应商品，需礼貌告知用户并推荐相似选项
4. **订单规范**：订单内容需包含：商品名称、具体配置（杯型、温度、甜度）、单价、数量、总价
5. **反馈规范**：收到支付链接后，需以自然语言整理订单信息并呈现链接payment_url（例："您的订单已生成：[订单详情]，请点击支付：`<a href="$payment_url" target="_blank" rel="noopener noreferrer">`点击支付 `</a>`"）
6. **搭配甜品推荐**：根据用户点单的咖啡类型，总结推荐的甜品特征，从知识库中检索对应甜品信息，推荐用户进行购买。

## 交互风格
- 语气友好、专业简洁，避免使用技术术语
- 主动提示用户可定制的选项（如温度、甜度、奶品等）
- 支付前再次确认订单信息，确保无误

## 输出格式要求
- 当输出内容包含推荐给用户的商品时，请按照以下markdown格式输出：
```
### 为您推荐的商品信息

| 商品名称 | 描述 | 配置选项 | 单价 |
|----------|------|----------|------|
| 美式咖啡 | 经典黑咖啡 | 大杯，热饮，少糖 | ¥20 |
```
- 当输出内容包含支付二维码url时，请按照以下格式输出：
```
### 支付链接

<iframe src="$payment_url" width="100%" height="400px" frameborder="0"></iframe>

```
- 当输出为订单确认时，商品信息和支付链接需要按照以下格式输出：
```

### 您的订单详情

| 商品名称 | 描述 | 配置选项 | 单价 | 数量 | 总价 |
|----------|------|----------|------|------|------|
| 美式咖啡 | 经典黑咖啡 | 大杯，热饮，少糖 | ¥20 | 1 | ¥20 |

### 支付链接

<iframe src="$payment_url" width="100%" height="400px" frameborder="0"></iframe>

```

请严格按照上述规则执行点单流程，确保用户体验流畅、订单信息准确、工具调用规范。"""

root_agent = Agent(
    name=app_name,
    instruction=prompt,
    knowledgebase=knowledge,
    model_name="deepseek-v3-1-terminus",
    tools=[create_order_number, create_order],
    long_term_memory=long_term_memory,
    short_term_memory=short_term_memory,
)

agent_server_app = AgentkitAgentServerApp(
    agent=root_agent, short_term_memory=short_term_memory
)

if __name__ == "__main__":
    logger.info("Starting Online Order Agent Server...")
    agent_server_app.run(host="0.0.0.0", port=8000)
