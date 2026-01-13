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

import os
import shutil
from typing import Optional, Any

from google.adk.tools import BaseTool, ToolContext
from veadk.utils.logger import get_logger

logger = get_logger(__name__)


def hook_tool_execute(
    tool: BaseTool, args: dict[str, Any], tool_context: ToolContext, tool_response: Any
) -> Optional[Any]:
    if tool.name == "video_combine":
        output_path = tool_response
        if output_path:
            tool_context.state["release_agent_local_dir"] = os.path.dirname(output_path)

    elif tool.name == "upload_file_to_tos":
        local_dir = tool_context.state.get("release_agent_local_dir", None)
        if local_dir and os.path.exists(local_dir):
            shutil.rmtree(local_dir)
    tool_context.state["cb_agent_state"] = "\n✅任务完成。\n"
    tool_context.state["cb_agent_output"] = ""
