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

from typing import Optional
from google.adk.tools.tool_context import ToolContext
from google.adk.tools.base_tool import BaseTool
from typing import Dict, Any
from veadk.utils.logger import get_logger

from app.utils import url_shortener

logger = get_logger(__name__)


def hook_short_image_url_to_long(
    tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext
) -> Optional[Dict]:
    """
    before_tool_callback hook function.
    """
    if tool.name == "video_generate":
        params = args["params"]
        for param in params:
            if param.get("first_frame", None):
                param["first_frame"] = url_shortener.code2url(
                    short_id=param["first_frame"]
                )


def get_callback_agent_output(success_list: list[dict[str, Any]]) -> str:
    """
    Get the callback agent output for video generation.
    """
    code_list = [[], [], [], []]
    for data in success_list:
        try:
            key_str = list(data.keys())[0]
            value_str = list(data.values())[0]  # url
            prefix, item = key_str.split("_video_")
            shot_num = prefix.split("shot_")[1]
            code_list[int(shot_num) - 1].append(value_str)
        except Exception as e:
            logger.error(f"Error in get_callback_agent_output: {e}")
            continue

    html_parts = []
    html_parts.append("\n\n### 视频展示")
    for shot_idx, codes in enumerate(code_list):
        if not codes:
            continue
        html_parts.append(f"#### Shot_{shot_idx + 1}\n")
        for video_idx, code in enumerate(codes):
            video_url = url_shortener.code2url(code)
            html_parts.append(f"{video_url} \n\n")
        html_parts.append("")

    return "\n\n".join(html_parts)


def hook_url_id_mapping(
    tool: BaseTool, args: dict[str, Any], tool_context: ToolContext, tool_response: Any
) -> Optional[Any]:
    """
    Shorten the URL.
    after_tool_callback
    """
    tool_name = tool.name
    if tool_name == "video_generate":
        success_list = tool_response["success_list"]

        tool_context.state["cb_agent_state"] = (
            "\n分镜视频生成任务已经完成，继续执行分镜视频评估工作\n"
        )
        tool_context.state["cb_agent_output"] = get_callback_agent_output(success_list)
        for data in success_list:
            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, str):
                        value = url_shortener.url2code(original_url=value)
                        data[key] = value
        logger.debug(f"Shorten URL of `video_generate` successfully: {success_list}")
        return tool_response
    return None
