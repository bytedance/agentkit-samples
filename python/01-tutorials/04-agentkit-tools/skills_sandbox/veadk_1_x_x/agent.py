import logging
import os
import sys

from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from agentkit.apps import AgentkitAgentServerApp
from veadk import Agent
from veadk.memory.short_term_memory import ShortTermMemory
from prompts.prompt import ROOT_AGENT_INSTRUCTION_CN, ROOT_AGENT_INSTRUCTION_EN

from google.adk.skills import load_skill_from_dir
from google.adk.tools.skill_toolset import SkillToolset
from veadk.skills import VeSkillRegistry

logger = logging.getLogger(__name__)

app_name = "skill_agent"
user_id = "skill_agent_user"
session_id = "skill_agent_session"

ROOT_AGENT_INSTRUCTION = ROOT_AGENT_INSTRUCTION_CN

provider = os.getenv("CLOUD_PROVIDER")
if provider and provider.lower() == "byteplus":
    ROOT_AGENT_INSTRUCTION = ROOT_AGENT_INSTRUCTION_EN


def _build_skill_toolset() -> SkillToolset | None:
    """
    Function Purpose:
        根据本地技能目录和远程 Skill Space 配置构建技能工具集。

    Implementation Logic:
        优先读取 SKILL_DIR；未配置时向上查找仓库内置技能目录。
        本地技能和远程注册表均为可选项，避免缺少任一配置时阻断 Agent 启动。
    """
    skill_dir_value = os.getenv("SKILL_DIR")
    if skill_dir_value:
        skill_dir = Path(skill_dir_value).expanduser()
    else:
        skill_dir = next(
            (
                parent / "skills" / "byted-music-generate"
                for parent in Path(__file__).resolve().parents
                if (parent / "skills" / "byted-music-generate").is_dir()
            ),
            None,
        )

    local_skills = []
    if skill_dir and skill_dir.is_dir():
        local_skills.append(load_skill_from_dir(str(skill_dir)))
    elif skill_dir:
        logger.warning("Skill directory does not exist: %s", skill_dir)

    skill_space_id = os.getenv("SKILL_SPACE_ID")
    remote_registry = (
        VeSkillRegistry(skill_source_id=skill_space_id) if skill_space_id else None
    )

    if not local_skills and remote_registry is None:
        logger.warning(
            "No local skill or SKILL_SPACE_ID configured; start without SkillToolset."
        )
        return None

    return SkillToolset(
        skills=local_skills or None,
        registry=remote_registry,
    )


skill_toolset = _build_skill_toolset()

agent = Agent(
    name="skill_agent",
    model_name=os.getenv("MODEL_AGENT_NAME", "deepseek-v4-pro-260425"),
    instruction=ROOT_AGENT_INSTRUCTION,
    tools=[skill_toolset] if skill_toolset else [],
)

short_term_memory = ShortTermMemory(backend="local")

# using veadk web for debugging
root_agent = agent

agent_server_app = AgentkitAgentServerApp(
    agent=agent,
    short_term_memory=short_term_memory,
)

if __name__ == "__main__":
    agent_server_app.run(host="0.0.0.0", port=8000)
