# 导入所有必要的模块
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv


# 将当前目录添加到sys.path以便本地模块导入
sys.path.append(str(Path(__file__).resolve().parent))
# 加载 settings.txt（dotenv 格式）
load_dotenv(
    dotenv_path=str(Path(__file__).resolve().parent / "settings.txt"), override=False
)

# 导入veadk和agentkit相关模块
from veadk import Agent, Runner  # noqa: E402
from veadk.auth.veauth.ark_veauth import get_ark_token  # noqa: E402
from veadk.memory.short_term_memory import ShortTermMemory  # noqa: E402
from veadk.tools.builtin_tools.video_generate import video_generate  # noqa: E402
from agentkit.apps import AgentkitAgentServerApp  # noqa: E402

# 导入本地模块
from tools.catalog_discovery import catalog_discovery  # noqa: E402
from tools.duckdb_sql_execution import duckdb_sql_execution  # noqa: E402
from tools.lancedb_hybrid_execution import lancedb_hybrid_execution  # noqa: E402
from prompts import SYSTEM_PROMPT  # noqa: E402

# Check if MODEL_AGENT_API_KEY environment variable exists and is not empty
if "MODEL_AGENT_API_KEY" not in os.environ or not os.environ["MODEL_AGENT_API_KEY"]:
    os.environ["MODEL_AGENT_API_KEY"] = get_ark_token()
# Optionally assign to a variable for easier use in the file
MODEL_AGENT_API_KEY = os.environ["MODEL_AGENT_API_KEY"]

short_term_memory = ShortTermMemory(backend="local")

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# --- Logging Configuration ---
logger = logging.getLogger(__name__)

tools = [
    catalog_discovery,
    duckdb_sql_execution,
    lancedb_hybrid_execution,
    video_generate,
]

# 创建带记忆的 Agent
model_name = os.getenv(
    "MODEL_AGENT_NAME", "doubao-seed-1-6-251015"
)  # 默认使用更主流的豆包模型
root_agent = Agent(
    description="基于LanceDB的数据检索Agent，支持结构化和向量查询。典型问题包括：1.你有哪些数据？2.给我一些样例数据？3.Ang Lee 评分超过7分的有哪些电影？4.Ang Lee 评分超过7分的电影中，有哪个电影海报中含有动物？5.Life of Pi 的电影海报，变成视频",
    instruction=SYSTEM_PROMPT,
    model_name=model_name,
    tools=tools,
    short_term_memory=short_term_memory,
)

runner = Runner(agent=root_agent)

# a2a_app = AgentkitA2aApp()

# @a2a_app.agent_executor(runner=runner)
# class MyAgentExecutor(A2aAgentExecutor):
#     pass

# # 当直接运行此文件时，启动本地服务
# if __name__ == "__main__":
#     logger.info("🚀 正在启动 A2A Agent 服务...")
#     a2a_app.run(
#         agent_card=get_agent_card(agent=root_agent, url="http://127.0.0.1:8000"),
#         host="0.0.0.0",
#         port=8000,
#     )

agent_server_app = AgentkitAgentServerApp(
    agent=root_agent,
    short_term_memory=short_term_memory,
)

if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
