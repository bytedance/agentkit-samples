# Copyright (c) 2026 ByteDance Ltd. and/or its affiliates
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
import sys
import json
import click
import qrcode
import logging
import jsonpath
import urllib.parse
from copy import deepcopy
from .base import Result

# 数据模版
TEMPLATE = {
    "common_data": {"initial_scene": 4},
    "infini_editor": {
        "instances": [{"resource": {"file_type": 2, "is_local": False, "url": ""}}]
    },
    "publish": {"text": {"body": ""}},
}


@click.command()
@click.option("--url", required=True, help="视频链接")
@click.option("--body", required=True, help="发布页正文")
@click.option("--output", "-o", required=True, help="二维码PNG图片本地保存路径")
def main(url, body, output):
    """抖音营销视频发布工具，参考[视频发布指南](references/视频发布指南.md)"""
    logging.info(f"[tool] >>> {' '.join(sys.argv)}")
    payload = deepcopy(TEMPLATE)
    resource = jsonpath.jsonpath(payload, "$.infini_editor.instances.0.resource")
    if resource:
        resource[0]["url"] = url
    text = jsonpath.jsonpath(payload, "$.publish.text")
    if text:
        text[0]["body"] = body
    # 将字典转换为紧凑的JSON字符串
    compact_json = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)

    # 构建schema URL
    schema = "aweme://studio/composer?config=" + urllib.parse.quote(compact_json)
    img = qrcode.make(data=schema)
    # 自动创建父目录
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    img.save(output, format="PNG")  # type: ignore

    # 这里必须开启ensure_ascii，否则无法跳转
    encoded_url = urllib.parse.quote(url)
    encoded_body = urllib.parse.quote(body)
    jump = (
        "https://magic.solutionsuite.cn/html-box/vev4VhD2gAY?url="
        + encoded_url
        + "&body="
        + encoded_body
    )
    result = Result(code="0", message="", data={"qrcode": output, "jump": jump})
    click.echo(result.model_dump_json())


if __name__ == "__main__":
    main()
