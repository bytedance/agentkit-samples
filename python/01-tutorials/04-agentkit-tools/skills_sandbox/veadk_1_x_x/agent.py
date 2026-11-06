import asyncio
import logging
import os
import sys

from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from agentkit.apps import AgentkitAgentServerApp
from google.adk.tools import ToolContext
from veadk import Agent, SkillSandboxAgent
from veadk.memory.short_term_memory import ShortTermMemory
from veadk.tools.builtin_tools.execute_skills import execute_skills as _execute_skills

logger = logging.getLogger(__name__)

app_name = "skill_agent"
user_id = "skill_agent_user"
session_id = "skill_agent_session"

ROOT_AGENT_INSTRUCTION_CN = """
你是一个技能执行小助手，但你不能直接执行技能，只能调用 execute_skills 工具。
收到任何需要技能能力、技能列表、文件处理、测试或自动化的请求时，都必须把用户请求原样整理为 workflow_prompt 后调用 execute_skills。
"""

ROOT_AGENT_INSTRUCTION_EN = """
You are a skill execution assistant. You cannot execute skills directly; you can only call the execute_skills tool.
For any request that needs skill capabilities, skill listing, file processing, testing, or automation, convert the user request into workflow_prompt and call execute_skills.
"""

SANDBOX_GUARDRAILS_CN = """
执行前请遵守以下约束：
1. 如果需要执行 Shell 命令，只能调用 bash_tool，禁止调用 bash。
2. 可用的技能环境工具名包括 skills_tool、read_file_tool、write_file_tool、edit_file_tool、bash_tool、register_skills_tool、update_check_list。
3. 如果用户只是要求测试 skill，请执行轻量测试：先列出可用技能，再选择一个不需要安装新依赖的最小动作验证工具链路。
4. 不要尝试向系统 Python 或 /opt/agentkit-skill/.venv 安装包；除非用户明确要求，否则不要安装依赖。
"""

SANDBOX_GUARDRAILS_EN = """
Before execution, follow these constraints:
1. If shell execution is needed, call bash_tool only. Do not call bash.
2. Available skill-environment tool names include skills_tool, read_file_tool, write_file_tool, edit_file_tool, bash_tool, register_skills_tool, and update_check_list.
3. If the user only asks to test skills, run a lightweight test: list available skills first, then choose a minimal action that does not require installing new dependencies.
4. Do not install packages into system Python or /opt/agentkit-skill/.venv. Unless explicitly requested by the user, do not install dependencies.
"""

ROOT_AGENT_INSTRUCTION = ROOT_AGENT_INSTRUCTION_CN
SANDBOX_GUARDRAILS = SANDBOX_GUARDRAILS_CN

provider = os.getenv("CLOUD_PROVIDER")
if provider and provider.lower() == "byteplus":
    ROOT_AGENT_INSTRUCTION = ROOT_AGENT_INSTRUCTION_EN
    SANDBOX_GUARDRAILS = SANDBOX_GUARDRAILS_EN

DEFAULT_MODEL_AGENT_NAME = (
    "deepseek-v4-1-flash-260910"
    if (provider and provider.lower() == "byteplus")
    or (not provider and os.getenv("BYTEPLUS_REGION"))
    else "doubao-seed-evolving"
)


async def execute_skills(
    workflow_prompt: str,
    tool_context: ToolContext = None,
    timeout: int = 1800,
) -> str:
    """Execute a workflow in Skill Sandbox and return its final result.

    Args:
        workflow_prompt: The complete user workflow to execute remotely.
        timeout: Maximum execution time in seconds, from 1 to 1800.
    """
    guarded_prompt = (
        f"{SANDBOX_GUARDRAILS}\n\n用户请求 / User request:\n{workflow_prompt}"
    )
    return await asyncio.to_thread(
        _execute_skills,
        workflow_prompt=guarded_prompt,
        tool_context=tool_context,
        timeout=timeout,
    )


agent = Agent(
    name="skill_agent",
    model_name=os.getenv("MODEL_AGENT_NAME", DEFAULT_MODEL_AGENT_NAME),
    instruction=ROOT_AGENT_INSTRUCTION,
    tools=[execute_skills],
)

short_term_memory = ShortTermMemory(backend="local")

# Keep the original LLM/function-tool path available for compatibility.
# The bridge streams remote events directly, without a second LLM rewriting them.
root_agent = (
    SkillSandboxAgent(name=app_name, guardrails=SANDBOX_GUARDRAILS, timeout=1800)
    if os.getenv("SKILL_SANDBOX_STREAMING", "true").lower() in {"true", "1", "yes"}
    else agent
)

agent_server_app = AgentkitAgentServerApp(
    agent=root_agent,
    short_term_memory=short_term_memory,
)

if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
