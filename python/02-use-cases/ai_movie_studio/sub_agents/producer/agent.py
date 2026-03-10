import os
import logging
from pathlib import Path

from veadk import Agent
from utils import (
    init_veadk_builtin_tools, 
    init_short_term_memory,
    init_long_term_memory,
    init_knowledge_base,
    init_prompt_manager, 
    init_observability, 
    load_local_instruction,
    callback_cleanup_model_output,
    callback_cleanup_tool_output
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 1. Identity & Config
app_name = os.getenv("VEADK_APP_NAME", "ai_movie_studio_producer")
agent_name = os.getenv("VEADK_AGENT_NAME", "producer_agent")
description = os.getenv("VEADK_APP_DESCRIPTION", "AI Movie Studio 团队成员之一，金牌制片人，负责统筹创意、制作与评审")
instruction_path = Path(__file__).parent / os.getenv("PROMPT_MANAGEMENT_LOCAL_INSTRUCTION_FILE", "instruction.md")

# 2. Components
short_term = init_short_term_memory(app_name)
long_term = init_long_term_memory(app_name)
knowledge = init_knowledge_base(app_name)
prompt_manager = init_prompt_manager()
tracers = init_observability()
instruction = load_local_instruction(instruction_path)

# 3. Tools
tools = init_veadk_builtin_tools()

# 4. Sub Agents (Lazy Load)
try:
    import sys
    # Add project root to sys.path to allow importing sub_agents
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
    if project_root not in sys.path:
        sys.path.append(project_root)
        
    from sub_agents.screenwriter.agent import agent as screenwriter_agent
    from sub_agents.director.agent import agent as director_agent
    from sub_agents.critic.agent import agent as critic_agent
    
    sub_agents = [screenwriter_agent, director_agent, critic_agent]
except ImportError as e:
    logger.warning(f"Failed to import local sub-agents: {e}. Running in Router-Only mode (Cloud mode).")
    sub_agents = []

# 5. Agent Definition
agent = Agent(
    name=agent_name,
    description=description,
    model_api_key=os.getenv("MODEL_AGENT_API_KEY", ""),
    tools=tools,
    sub_agents=sub_agents,
    short_term_memory=short_term,
    long_term_memory=long_term,
    knowledgebase=knowledge,
    prompt_manager=prompt_manager,
    tracers=tracers,
    instruction=instruction,
    after_model_callback=callback_cleanup_model_output,
    after_tool_callback=callback_cleanup_tool_output,
    auto_save_session=bool(long_term),
    enable_responses=True,
)
