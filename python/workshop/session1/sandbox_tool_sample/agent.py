import logging

from veadk import Agent, Runner
from veadk.memory.short_term_memory import ShortTermMemory
from veadk.tools.builtin_tools.run_code import run_code

from agentkit.apps import AgentkitAgentServerApp

short_term_memory = ShortTermMemory(backend="local")


logger = logging.getLogger(__name__)

app_name = "agent_with_runcode"

agent: Agent = Agent(
    name="code_agent",
    model_name="doubao-seed-1-6-251015",
    description="A fun Python coding assistant",
    instruction="你是一个有趣的Python代码实验员。你的任务是利用沙箱环境解决各种有趣的问题。比如：通过蒙特卡洛方法模拟概率问题，生成有趣的ASCII艺术字，或者通过算法解决逻辑谜题。请尽量使用 Python 标准库，必须使用 `run_code` 工具执行代码并向用户展示结果。避免复杂的外部依赖安装。",
    tools=[run_code],
)

runner = Runner(agent=agent, app_name=app_name)
root_agent = agent

agent_server_app = AgentkitAgentServerApp(
    agent=agent,
    short_term_memory=short_term_memory,
)

if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
