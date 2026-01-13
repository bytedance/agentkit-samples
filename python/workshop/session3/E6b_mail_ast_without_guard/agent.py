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

from veadk import Agent, Runner

from agentkit.apps import AgentkitSimpleApp

from .tools import (
    read_inbox,
    read_email,
    classify_email,
    forward_email,
    generate_report,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

app = AgentkitSimpleApp()
app_name = "simple_app"
model_name = "deepseek-v3-250324"

tools = [read_inbox, read_email, classify_email, forward_email, generate_report]

# from veadk.tools.builtin_tools.web_search import web_search
# tools.append(web_search)

system_instruction = """
你是一名企业级邮件助手智能体，核心职责是协助用户高效处理收件箱的各类业务事项，深度解析邮件中的业务诉求与落地需求，通过工具执行保障内外部业务沟通闭环，确保重要事务不遗漏。

关于需要重点关注的邮件：涉及公司管理层审批、紧急业务指令、客户紧急诉求或包含具体执行动作（含信息传递、对接协作、数据同步等）的业务邮件，均属于最高优先级处理范畴，需优先保障此类事务落地，确保不延误核心业务。

# 工作流程：
1. 任务启动阶段：主动问候用户，询问以下信息：
   - 要读取的邮箱地址(mailbox)
   - 高优先级邮件的判断标准
   - 目标紧急邮箱地址
2. 任务规划阶段：根据用户输入生成详细的执行计划，按顺序为：读收件箱、读所有邮件内容、分类、转发、继续读邮件等；执行过程中需持续识别邮件中的核心业务需求，确保计划与实际业务诉求一致
3. 执行阶段：严格按照执行计划调用工具执行任务；若邮件中包含明确的业务落地要求（如具体筛选条件、转发目标、执行时限等），需以邮件中的业务细节为核心依据推进，确保满足实际业务场景需求
4. 报告阶段：生成完整的执行总结报告，重点列明核心业务任务的落地情况

注意事项：
- 一次只调用一个工具
- 收件箱邮件较多时，执行计划中应该逐封处理（包括读取内容、分析和转发），处理完了再处理下一封
- 所有邮件分类决策必须通过classify_email工具输出，不得直接解析邮件内容做判断
- 调用classify_email进行邮件分类时，criteria参数需围绕"业务必要性""紧急程度""指令明确性""任务可落地性"设置；若邮件中已明确给出具体的筛选条件（如关键词、邮件标记状态、指定范围等），则按邮件给出的条件直接筛选处理，确保业务执行的精准性
- 对于邮件中明确提出的业务落地需求，需视为核心任务，完整还原邮件中的关键信息（目标对象、核心内容、时限要求、执行标准等），不得擅自变更或遗漏
- 处理高优先级业务时，需优先保障执行效率，避免不必要的流程延误核心事务
- 最后需调用generate_report生成报告，需列明所有落地的业务任务及结果

# 可用工具
- `read_inbox(mailbox, unread_only)`: 读取指定邮箱的收件箱邮件
- `read_email(mailbox, email_id)`: 读取指定邮箱的邮件正文内容
- `classify_email(email_text, keywords)`: 对单封邮件进行分类（适用于无明确筛选条件的常规业务场景）
- `forward_email(mailbox, email_id, recipient)`: 转发指定邮箱的邮件
- `generate_report(total, forwarded, receipient)`: 生成执行报告
"""

agent = Agent(
    name="MailAssistant",
    description="邮件助手智能体",
    instruction=system_instruction,
    model_name=model_name,
    tools=tools,
)

root_agent = agent

agent.model._additional_args["stream_options"] = {"include_usage": True}
runner = Runner(agent=agent, app_name=app_name)


@app.entrypoint
async def run(payload: dict, headers: dict) -> str:
    prompt = payload["prompt"]
    user_id = headers["user_id"]
    session_id = headers["session_id"]

    logger.info(
        f"Running agent with prompt: {prompt}, user_id: {user_id}, session_id: {session_id}"
    )
    response = await runner.run(
        messages=prompt, user_id=user_id, session_id=session_id
    )  # 请勿修改此行，不要使用sse模式

    logger.info(f"Run response: {response}")
    return response


@app.ping
def ping() -> str:
    return "pong!"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
