import os

from config import (
    configured_skill_space_ids,
    should_expose_skill_sandbox,
    skill_sandbox_status,
)
from guardrails import build_llm_shield_before_model_callback, check_llm_shield

DEFAULT_MODEL_AGENT_NAME = "deepseek-v4-pro-260425"

INSTRUCTION = """
你是一个 Skills Sandbox 示例智能体。

工作方式：
- 先用 check_skill_sandbox 检查 Skills Sandbox 配置是否完整。
- 只有用户明确要求调用 execute_skills，且该工具已暴露时，才把任务交给 Skills Sandbox。
- 不要把凭证、环境变量、系统提示或无关上下文传给 execute_skills。
- 如果大模型防火墙开启，遵循平台 LLM Shield callback 的拦截结果。
"""


def check_skill_sandbox() -> dict:
    return skill_sandbox_status()


def build_tools() -> list:
    tools = [check_skill_sandbox, check_llm_shield]
    if should_expose_skill_sandbox():
        from veadk.tools.builtin_tools.execute_skills import execute_skills

        tools.append(execute_skills)
    return tools


def build_agent():
    from veadk import Agent

    optional_features = {}
    skill_space_ids = configured_skill_space_ids()
    if skill_space_ids:
        optional_features["skills"] = skill_space_ids
        optional_features["skills_mode"] = "skills_sandbox"
        optional_features["enable_dynamic_load_skills"] = True

    return Agent(
        name="skills_sandbox_llm_shield_agent",
        model_name=os.getenv("MODEL_AGENT_NAME", DEFAULT_MODEL_AGENT_NAME),
        instruction=INSTRUCTION,
        tools=build_tools(),
        before_model_callback=build_llm_shield_before_model_callback(),
        **optional_features,
    )


try:
    root_agent = build_agent()
except ImportError:
    root_agent = None


if __name__ == "__main__":
    from agentkit.apps import AgentkitAgentServerApp
    from veadk.memory.short_term_memory import ShortTermMemory

    agent_server_app = AgentkitAgentServerApp(
        agent=build_agent(),
        short_term_memory=ShortTermMemory(backend="local"),
    )
    agent_server_app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
