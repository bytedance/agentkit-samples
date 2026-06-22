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
ByteHouse 知识库文件列表查询脚本
用于查询ByteHouse知识库中的文件列表

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


def list_files_in_kb(kb_id: int) -> dict:
    """
    查询知识库文件列表
    
    Args:
        kb_id: 知识库ID
    
    Returns:
        API返回结果
    """
    if not BYTEHOUSE_HOST:
        print("Error: Please set BYTEHOUSE_HOST environment variable", file=sys.stderr)
        sys.exit(1)
    
    url = build_kb_api_url(BYTEHOUSE_HOST, 'knowledge-base/file/list')
    auth_token = BYTEHOUSE_PASSWORD if BYTEHOUSE_PASSWORD else ""
    
    headers = {
        "Content-Type": "application/json",
    }
    
    # 添加认证
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    
    # 构建请求 payload
    payload = {
        "knowledgeBaseID": kb_id
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=15)
    response.raise_for_status()
    
    return response.json()


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description='ByteHouse 知识库文件列表查询工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  # 查询指定知识库中的文件列表
  python3 list_files_in_kb.py --kb-id 123

环境变量:
  BYTEHOUSE_HOST      - ByteHouse 主机 (如 tenant-xxx-cn-beijing-public.bytehouse.volces.com)
  BYTEHOUSE_PASSWORD  - 密码 (作为 Bearer token)
'''
    )
    
    parser.add_argument('--kb-id', type=int, required=True, help='指定要查询的知识库ID（必填）')
    
    args = parser.parse_args()
    
    try:
        kb_id = args.kb_id
        result = list_files_in_kb(kb_id)
        print(f"查询成功！知识库ID: {kb_id}")
        print(f"返回结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
