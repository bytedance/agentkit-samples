#!/usr/bin/env python3
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

"""
ByteHouse 知识库问答脚本
用于通过自然语言向ByteHouse知识库提问，获取流式回复

配置方式：设置以下环境变量
- BYTEHOUSE_HOST: ByteHouse 主机地址 (如 tenant-xxx-cn-beijing-public.bytehouse.volces.com)
- BYTEHOUSE_PASSWORD: 密码 (用作 Bearer token)
"""

import os
import requests
import json
import sys
import argparse

# 从环境变量读取默认配置
BYTEHOUSE_HOST = os.environ.get('BYTEHOUSE_HOST', '')
BYTEHOUSE_PASSWORD = os.environ.get('BYTEHOUSE_PASSWORD', '')


def build_kb_api_url(host: str, endpoint: str) -> str:
    """构建知识库API URL"""
    if not host:
        print("Error: BYTEHOUSE_HOST environment variable is required", file=sys.stderr)
        sys.exit(1)
    
    # 处理 host - 可能是 host:port 格式
    if host.startswith('http'):
        base_url = host.rstrip('/')
    else:
        base_url = f"https://{host}"
    
    return f"{base_url}/matrix/v1/{endpoint.lstrip('/')}"


def knowledge_base_chat(kb_ids: list[int], input_text: str) -> None:
    """
    与知识库进行流式对话
    
    Args:
        kb_ids: 知识库ID列表
        input_text: 用户输入的自然语言
    """
    if not BYTEHOUSE_HOST:
        print("Error: Please set BYTEHOUSE_HOST environment variable", file=sys.stderr)
        sys.exit(1)
    
    url = build_kb_api_url(BYTEHOUSE_HOST, 'knowledge-base/stream-chat')
    auth_token = BYTEHOUSE_PASSWORD if BYTEHOUSE_PASSWORD else ""
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream"
    }
    
    # 添加认证
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    
    # 构建请求 payload
    payload = {
        "knowledgeBaseIDs": [str(kb_id) for kb_id in kb_ids],
        "input": input_text,
        "sessionID": "",
        "trashSessionID": ""
    }
    
    print(f"正在向知识库提问: {input_text}")
    print("-" * 80)
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60, stream=True)
        response.raise_for_status()
        
        # 处理流式响应
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data:'):
                    data_str = line_str[5:].strip()
                    try:
                        data = json.loads(data_str)
                        event_type = data.get('event_type')
                        
                        if event_type == 'DONE':
                            break
                        elif event_type == 'DELTA':
                            event_data_str = data.get('event_data', '{}')
                            event_data = json.loads(event_data_str)
                            content = event_data.get('message', {}).get('content', '')
                            if content:
                                print(content, end='', flush=True)
                    except json.JSONDecodeError:
                        pass
        print("\n" + "-" * 80)
    except requests.exceptions.RequestException as e:
        print(f"\nError connecting to API: {e}", file=sys.stderr)
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}", file=sys.stderr)
        sys.exit(1)


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description='ByteHouse 知识库问答工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  # 向单个知识库提问
  python3 knowledge_base_chat.py --kb-ids 123 --input "什么是ByteHouse？"
  
  # 向多个知识库提问
  python3 knowledge_base_chat.py --kb-ids 123 456 --input "如何创建表？"

环境变量:
  BYTEHOUSE_HOST      - ByteHouse 主机 (如 tenant-xxx-cn-beijing-public.bytehouse.volces.com)
  BYTEHOUSE_PASSWORD  - 密码 (作为 Bearer token)
'''
    )
    
    parser.add_argument('--kb-ids', type=int, nargs='+', required=True, help='指定一个或多个知识库ID（必填，空格分隔）')
    parser.add_argument('--input', type=str, required=True, help='用户的自然语言输入（必填）')
    
    args = parser.parse_args()
    
    try:
        knowledge_base_chat(args.kb_ids, args.input)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
