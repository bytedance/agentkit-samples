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
app_name = os.getenv("VEADK_APP_NAME", "ai_movie_studio_screenwriter")
agent_name = os.getenv("VEADK_AGENT_NAME", "screenwriter_agent")
description = os.getenv("VEADK_APP_DESCRIPTION", "AI Movie Studio 团队成员之一，首席编剧，负责剧本创作与分镜设计")
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

# 4. Agent Definition
agent = Agent(
    name=agent_name,
    description=description,
    model_api_key=os.getenv("MODEL_AGENT_API_KEY", ""),
    tools=tools,
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
