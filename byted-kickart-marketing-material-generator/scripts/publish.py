import os
import sys
import json
import qrcode
import logging
import jsonpath
import subprocess
import urllib.parse
import click
from copy import deepcopy
from base import Result

# 数据模版
TEMPLATE = {
    "common_data": {"initial_scene": 4},
    "infini_editor": {
        "instances": [{"resource": {"file_type": 2, "is_local": False, "url": ""}}]
    },
    "publish": {"text": {"body": ""}},
}


def upload(url, body, output, conversation, metadata):
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

    # 通过工具将二维码发送给用户
    metadata = json.loads(metadata)
    conversation = json.loads(conversation)
    cmd = [
        "openclaw",
        "message",
        "send",
        "--media",
        output,
        "-t",
        metadata["chat_id"],
        "--reply-to",
        conversation["message_id"],
    ]
    logging.info(f"[openclaw] >>> {' '.join(cmd)}")
    retcode = subprocess.call(cmd)
    logging.info(f"[openclaw] >>> return code = {retcode}")

    # 这里必须开启ensure_ascii，否则无法跳转
    encoded_url = urllib.parse.quote(url)
    encoded_body = urllib.parse.quote(body)
    jump = (
        "https://magic.solutionsuite.cn/html-box/vev4VhD2gAY?url="
        + encoded_url
        + "&body="
        + encoded_body
    )
    return Result(code="0", message="", data={"qrcode": output, "jump": jump})


@click.command()
@click.option("--url", required=True, help="视频链接")
@click.option("--body", required=True, help="发布页正文")
@click.option("--output", "-o", required=True, help="二维码PNG图片本地保存路径")
@click.option(
    "--conversation", required=True, type=str, help="当前消息的完整未修改上下文元数据"
)
@click.option("--metadata", required=True, type=str, help="当前消息的完整未修改元信息")
def main(url, body, output, conversation, metadata):
    """视频发布到抖音平台"""
    logging.info(f"[tool] >>> python3 {' '.join(sys.argv)}")
    result = upload(
        url=url, body=body, output=output, conversation=conversation, metadata=metadata
    )
    print(result)


if __name__ == "__main__":
    main()
