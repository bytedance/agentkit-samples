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
    callback_cleanup_tool_output,
)

logger = logging.getLogger(__name__)

app_name = os.getenv("VEADK_APP_NAME", "carselector_unified")
agent_name = os.getenv("VEADK_AGENT_NAME", app_name)
description = os.getenv("VEADK_APP_DESCRIPTION", "智能选车助手（Unified）")

APP_NAME = app_name
DESCRIPTION = description

instruction_file = os.getenv("PROMPT_MANAGEMENT_LOCAL_INSTRUCTION_FILE", "instruction.md").strip()
instruction_path = Path(instruction_file)
if not instruction_path.is_absolute():
    instruction_path = Path(__file__).parent / instruction_path

short_term = init_short_term_memory(app_name)
long_term = init_long_term_memory(app_name)
knowledge = init_knowledge_base(app_name)
prompt_manager = init_prompt_manager()
tracers = init_observability()
instruction = load_local_instruction(instruction_path)

tools = init_veadk_builtin_tools()

enable_responses = os.getenv("VEADK_ENABLE_RESPONSES", "false").strip().lower() in {"1", "true", "yes"}

agent_kwargs = {
    "name": agent_name,
    "description": description,
    "model_api_key": os.getenv("MODEL_AGENT_API_KEY", ""),
    "tools": tools,
    "after_model_callback": callback_cleanup_model_output,
    "after_tool_callback": callback_cleanup_tool_output,
    "short_term_memory": short_term,
    "auto_save_session": bool(long_term),
    "enable_responses": enable_responses,
}

optional_kwargs = {
    "knowledgebase": knowledge,
    "long_term_memory": long_term,
    "instruction": instruction,
    "prompt_manager": prompt_manager,
    "tracers": tracers or None,
}
agent_kwargs.update({k: v for k, v in optional_kwargs.items() if v})

car_unified_agent = Agent(**agent_kwargs)
root_agent = car_unified_agent
