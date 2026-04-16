import os
import sys
import json
import urllib.parse
import qrcode
import argparse
import jsonpath
import subprocess
from copy import deepcopy
from model import *

# 数据模版
TEMPLATE = {
    "common_data": {"initial_scene": 4},
    "infini_editor": {
        "instances": [
            {
                "resource": {
                    "file_type": 2,
                    "is_local": False,
                    "url": ""
                }
            }
        ]
    },
    "publish": {
        "text": {
            "body": ""
        }
    }
}

def upload(args: argparse.Namespace):
    payload = deepcopy(TEMPLATE)
    resource = jsonpath.jsonpath(payload, "$.infini_editor.instances.0.resource")
    if resource: resource[0]['url'] = args.url
    text = jsonpath.jsonpath(payload, "$.publish.text")
    if text: text[0]['body'] = args.body
    # 将字典转换为紧凑的JSON字符串
    compact_json = json.dumps(payload, separators=(',', ':'), ensure_ascii=False)

    # 构建schema URL
    schema = 'aweme://studio/composer?config=' + urllib.parse.quote(compact_json)
    img = qrcode.make(data=schema)
    # 自动创建父目录
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    img.save(args.output, format="PNG")

    # 通过工具将二维码发送给用户
    metadata = json.loads(args.metadata)
    conversation = json.loads(args.conversation)
    cmd = ["openclaw", "message", "send", "--media", args.output, "-t", metadata['chat_id'], "--reply-to", conversation['message_id']]
    logging.info(f"[openclaw] >>> {' '.join(cmd)}")
    retcode = subprocess.call(cmd)
    logging.info(f"[openclaw] >>> return code = {retcode}")

    # 这里必须开启ensure_ascii，否则无法跳转
    encoded_url = urllib.parse.quote(args.url)
    encoded_body = urllib.parse.quote(args.body)
    jump = "https://magic.solutionsuite.cn/html-box/vev4VhD2gAY?url=" + encoded_url + "&body=" + encoded_body
    return Result(code='0', message="", data={"qrcode": args.output, "jump": jump})

if __name__ == "__main__":
    logging.info(f"[tool] >>> python3 {' '.join(sys.argv)}")
    parser = argparse.ArgumentParser(description="视频发布到抖音平台")
    parser.add_argument("--url", required=True, help="视频链接")
    parser.add_argument("--body", required=True, help="发布页正文")
    parser.add_argument("--output", "-o", required=True, help=f"二维码PNG图片本地保存路径")
    parser.add_argument("--conversation", required=True, type=str, help="当前消息的完整未修改上下文元数据")
    parser.add_argument("--metadata", required=True, type=str, help="当前消息的完整未修改元信息")
    args = parser.parse_args()

    # 默认二维码保存路径
    print(upload(args=args))