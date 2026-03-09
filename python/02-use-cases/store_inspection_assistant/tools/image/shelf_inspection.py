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
import logging
from tools.model_auth import get_ark_api_key, get_base_url
from prompts.prompt import (
    shelf_display_detection_tool_prompt_cn,
    shelf_display_detection_tool_prompt_en,
    shelf_inspection_wearing_detection_tool_prompt_cn,
    shelf_inspection_wearing_detection_tool_prompt_en,
)
from volcenginesdkarkruntime import Ark
import os


logger = logging.getLogger(__name__)

client = Ark(
    api_key=get_ark_api_key(),
    base_url=get_base_url(),
    timeout=1800,
)

shelf_display_detection_tool_prompt = ""
shelf_inspection_wearing_detection_tool_prompt = ""
provider = os.getenv("CLOUD_PROVIDER")
if provider and provider.lower() == "byteplus":
    shelf_display_detection_tool_prompt = shelf_display_detection_tool_prompt_en
    shelf_inspection_wearing_detection_tool_prompt = (
        shelf_inspection_wearing_detection_tool_prompt_en
    )
else:
    shelf_display_detection_tool_prompt = shelf_display_detection_tool_prompt_cn
    shelf_inspection_wearing_detection_tool_prompt = (
        shelf_inspection_wearing_detection_tool_prompt_cn
    )


def shelf_display_detection_tool(image_url: str) -> str:
    """
    Shelf display detection tool, input shelf image URL, return shelf display detection result
    Args:
        image_url (str): Shelf image URL
    Returns:
        str: Shelf display detection result
    """

    logger.debug(f"Running shelf_display_detection_tool with image_url: {image_url}")
    prompt = shelf_display_detection_tool_prompt
    response = client.chat.completions.create(
        model="seed-1-6-250915",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url, "detail": "high"},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        thinking={"typed": "enabled"},
        reasoning_effort="high",
    )
    return response.choices[0].message.content


def wearing_detection_tool(image_url: str) -> str:
    """
    Worker attire detection tool, input worker image URL, return worker attire detection result
    Args:
        image_url (str): Worker image URL
    Returns:
        str: Worker attire detection result
    """

    logger.debug(f"Running wearing_detection_tool with image_url: {image_url}")
    prompt = shelf_inspection_wearing_detection_tool_prompt
    response = client.chat.completions.create(
        model="seed-1-6-250915",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url, "detail": "high"},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        thinking={"typed": "enabled"},
        reasoning_effort="high",
    )
    return response.choices[0].message.content
