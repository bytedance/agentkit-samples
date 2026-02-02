import sys
import os

from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from agentkit.apps import AgentkitAgentServerApp
from veadk import Agent, Runner
from veadk.memory import ShortTermMemory

from callbacks import (
    after_agent_callback,
    after_model_callback,
    after_tool_callback,
    before_agent_callback,
    before_model_callback,
    before_tool_callback,
)
from tools import write_article
from prompts.prompt import ROOT_AGENT_INSTRUCTION_CN, ROOT_AGENT_INSTRUCTION_EN

ROOT_AGENT_INSTRUCTION = ROOT_AGENT_INSTRUCTION_CN

provider = os.getenv("CLOUD_PROVIDER")
if provider and provider.lower() == "byteplus":
    ROOT_AGENT_INSTRUCTION = ROOT_AGENT_INSTRUCTION_EN

root_agent = Agent(
    name="ChineseContentModerator",
    model_name=os.getenv("MODEL_AGENT_NAME", "deepseek-v3-2-251201"),
    description="一个演示全链路回调和护栏功能的中文内容审查助手。",
    instruction=ROOT_AGENT_INSTRUCTION,
    tools=[write_article],
    before_agent_callback=before_agent_callback,
    before_model_callback=before_model_callback,
    after_model_callback=after_model_callback,
    before_tool_callback=before_tool_callback,
    after_tool_callback=after_tool_callback,
    after_agent_callback=after_agent_callback,
)

runner = Runner(agent=root_agent)
short_term_memory = ShortTermMemory(backend="local")
agent_server_app = AgentkitAgentServerApp(
    agent=root_agent,
    short_term_memory=short_term_memory,
)


if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
