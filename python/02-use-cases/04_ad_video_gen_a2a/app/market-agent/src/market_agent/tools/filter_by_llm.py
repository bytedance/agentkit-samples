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

import asyncio
import json
import os
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel
from veadk.utils.logger import get_logger

logger = get_logger(__name__)

filter_agent_instructions = """
你是一个专业的图片过滤器，服务于一个商品图片相关的任务
你将收到一张图片输入，他来自于一个网页的链接，通过网页解析等机制解析下来的，
你需要根据图片的内容判断这张图片是商品，还是类似网页素材，点缀之类的无关内容。
你不需要返回任何判断，你只需要确定是与否，不允许任何额外的输出
注意如果你不能确定是否是商品，那它就不是。

### 参考输出
{
    "is_good": true
}
"""

summarize_text_instructions = """
你是一个专业的文本总结器，服务于一个商品图片相关的任务
你将收到一段文本输入，他来自于一个网页的链接，通过网页解析等机制解析下来的，
你需要根据文本的内容总结出这段文本的主要内容，包括商品的名称、价格、描述、特点等。
"""


class IsGood(BaseModel):
    is_good: bool


def repair_image_input(image_list: list[str]) -> list[dict[str, Any]]:
    result = []
    for image in image_list:
        image_part = {
            "type": "input_image",
            "image_url": image,
        }  # 参考的只会是图片
        result.append(image_part)

    return result


async def filter_images(image_list: list[str]) -> list[str]:
    inputs = repair_image_input(image_list)
    client = AsyncOpenAI(
        base_url=os.getenv("MODEL_AGENT_API_BASE"),
        api_key=os.getenv("MODEL_AGENT_API_KEY"),
    )
    sem = asyncio.Semaphore(10)  # 限制并发

    async def process_message(_input):
        async with sem:
            try:
                response = await client.responses.create(
                    model="doubao-seed-1-6-251015",
                    instructions=filter_agent_instructions,
                    input=[{"role": "user", "content": [_input]}],
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": "IsGood",
                            "schema": IsGood.model_json_schema(),
                            "strict": True,
                        }
                    },
                    extra_body={"thinking": {"type": "disabled"}},
                )
                x = json.loads(response.output_text).get("is_good", False)
            except Exception:
                x = False
            return _input["image_url"] if x else None

    result = await asyncio.gather(*(process_message(_input) for _input in inputs))
    result = [r for r in result if r is not None]
    return result


async def summarize_text(text: str):
    client = AsyncOpenAI(
        base_url=os.getenv("MODEL_AGENT_API_BASE"),
        api_key=os.getenv("MODEL_AGENT_API_KEY"),
    )
    try:
        response = await client.responses.create(
            model="doubao-seed-1-6-251015",
            instructions=summarize_text_instructions,
            input=text[0:10000],
            extra_body={"thinking": {"type": "disabled"}},
        )
        return response.output_text
    except Exception:
        return text[0:10000]
