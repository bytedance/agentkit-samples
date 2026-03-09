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
from app.utils import url_shortener

logger = get_logger(__name__)


def url_id_mapping(url: str) -> str:
    return url_shortener.url2code(original_url=url)


def get_callback_agent_output(success_list: list[dict[str, Any]]) -> str:
    """
    Get the callback agent output.
    """
    url_list = [[], [], [], []]
    for data in success_list:
        try:
            key_str = list(data.keys())[0]
            value_str = list(data.values())[0]  # url
            prefix, item = key_str.split("_image_")
            itx = prefix.split("task_")[1]
            url_list[int(itx)].append(value_str)
        except Exception as e:
            logger.error(f"Error in get_callback_agent_output: {e}")
            continue

    html_parts = []
    html_parts.append("\n\n### 图片生成结果")
    for task_idx, urls in enumerate(url_list):
        if not urls:
            continue
        html_parts.append(f"#### Shot_{task_idx}")
        for img_idx, url in enumerate(urls):
            html_parts.append(f"**Image_{img_idx + 1}：{url_id_mapping(url)}**")
            html_parts.append(f'<img src="{url}" alt="image" style="width: 10%;" />')
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
    if tool_name == "image_generate":
        success_list = tool_response["success_list"]

        tool_context.state["cb_agent_state"] = (
            "\n✅首帧图生成任务已经完成，继续执行首帧图评估工作\n"
        )
        tool_context.state["cb_agent_output"] = get_callback_agent_output(success_list)
        for data in success_list:
            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, str):
                        value = url_id_mapping(url=value)
                        data[key] = value
        logger.debug(f"Shorten URL of `image_generate` successfully: {success_list}")
        return tool_response
    return None
