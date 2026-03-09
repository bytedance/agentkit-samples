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

from typing import Any, Optional
from google.adk.tools import BaseTool, ToolContext
from veadk.utils.logger import get_logger

logger = get_logger(__name__)


def direct_output_callback(
    tool: BaseTool, args: dict[str, Any], tool_context: ToolContext, tool_response: dict
) -> Optional[dict]:
    """让工具结果直接输出，跳过LLM总结"""
    # 设置跳过总结标志
    if tool.name == "evaluate_media":
        tool_context.actions.skip_summarization = True
    return tool_response  # 不能return None
