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

# Check if MODEL_AGENT_API_KEY environment variable exists and is not empty
if "MODEL_AGENT_API_KEY" not in os.environ or not os.environ["MODEL_AGENT_API_KEY"]:
    os.environ["MODEL_AGENT_API_KEY"] = get_ark_token()

from veadk.tools.builtin_tools.video_generate import video_generate  # noqa: E402
from agentkit.apps import AgentkitAgentServerApp  # noqa: E402

# 导入本地模块
from tools.catalog_discovery import catalog_discovery  # noqa: E402
from tools.duckdb_sql_execution import duckdb_sql_execution  # noqa: E402
from tools.lancedb_hybrid_execution import lancedb_hybrid_execution  # noqa: E402
from prompts import SYSTEM_PROMPT_CN, SYSTEM_PROMPT_EN  # noqa: E402


# 根据 CLOUD_PROVIDER 环境变量选择语言
provider = os.getenv("CLOUD_PROVIDER")
if provider and provider.lower() == "byteplus":
    SYSTEM_PROMPT = SYSTEM_PROMPT_EN
else:
    SYSTEM_PROMPT = SYSTEM_PROMPT_CN

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
model_name = os.getenv("MODEL_AGENT_NAME", "deepseek-v3-2-251201")
root_agent = Agent(
    description="基于LanceDB的数据检索Agent，支持结构化和向量查询。典型问题包括：1.你有哪些数据？2.给我一些样例数据？3.Ang Lee 评分超过7分的有哪些电影？4.Ang Lee 评分超过7分的电影中，有哪个电影海报中含有动物？5.Life of Pi 的电影海报，变成视频。 返回显示电影海报为![老虎](https://example.com/image1.png), 返回视频并显示成<video src='https://example.com/video1.mp4' width='640' controls>分镜视频1</video>",
    instruction=SYSTEM_PROMPT,
    model_name=model_name,
    tools=tools,
    short_term_memory=short_term_memory,
)

runner = Runner(agent=root_agent)


agent_server_app = AgentkitAgentServerApp(
    agent=root_agent,
    short_term_memory=short_term_memory,
)

if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
