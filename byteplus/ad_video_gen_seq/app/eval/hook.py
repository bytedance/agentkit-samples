# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Optional, Any

from google.adk.tools import BaseTool, ToolContext
from veadk.utils.logger import get_logger

logger = get_logger(__name__)


def hook_url_id_mapping(
    tool: BaseTool, args: dict[str, Any], tool_context: ToolContext, tool_response: Any
) -> Optional[Any]:
    """
    Handle evaluation results and generate callback output.
    after_tool_callback
    """
    agent_name = tool_context.agent_name
    tool_name = tool.name

    if tool_name == "evaluate_media":
        if agent_name == "image_evaluate_agent":
            tool_context.state["cb_agent_state"] = (
                "\n✅ First-frame image evaluation complete; proceeding to video generation\n"
            )
            tool_context.state["cb_agent_output"] = ""
        elif agent_name == "video_evaluate_agent":
            tool_context.state["cb_agent_state"] = (
                "\n✅ Video evaluation complete; proceeding to video composition\n"
            )
            tool_context.state["cb_agent_output"] = ""

        return tool_response

    return None
