import sys
import os

from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from agentkit.apps import AgentkitAgentServerApp
from veadk import Agent
from veadk.memory.short_term_memory import ShortTermMemory
from prompts.prompt import ROOT_AGENT_INSTRUCTION_CN, ROOT_AGENT_INSTRUCTION_EN

from google.adk.skills import load_skill_from_dir
from google.adk.tools.skill_toolset import SkillToolset
from veadk.skills import VeSkillRegistry

app_name = "skill_agent"
user_id = "skill_agent_user"
session_id = "skill_agent_session"

ROOT_AGENT_INSTRUCTION = ROOT_AGENT_INSTRUCTION_CN

provider = os.getenv("CLOUD_PROVIDER")
if provider and provider.lower() == "byteplus":
    ROOT_AGENT_INSTRUCTION = ROOT_AGENT_INSTRUCTION_EN

SKILL_DIR = "/Users/bytedance/work/wm_project/agentkit/volcengine-agentkit-samples/skills/byted-music-generate"
SKILL_SPACE_ID = "ss-xxx"  # agentkit skills space id
# SKILL_SPACE_ID = "sp-xxx"  # skillhub space id

# load skill from local dir
local_skill = load_skill_from_dir(SKILL_DIR)
# load skll from VeSkillRegistry
remote_registry = VeSkillRegistry(
    skill_source_id=SKILL_SPACE_ID,
)
skill_toolset = SkillToolset(
    # case1: if you have local skills
    # skills=[lcoal_skill]
    # case2: if you have remote skills registry
    # registry=remote_registry
    # case3: if you have both local skills and remote skills registry
    skills=[local_skill],
    registry=remote_registry,
)

agent = Agent(
    name="skill_agent",
    model_name=os.getenv("MODEL_AGENT_NAME", "deepseek-v4-pro-260425"),
    instruction=ROOT_AGENT_INSTRUCTION,
    tools=[skill_toolset],
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
