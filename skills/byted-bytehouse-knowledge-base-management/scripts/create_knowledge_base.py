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
ByteHouse 知识库创建脚本
用于创建ByteHouse知识库并返回知识库ID

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
IDENTITY_PATH = '/root/.openclaw/workspace/IDENTITY.md'
ENV_PATH = os.path.expanduser("~/.openclaw/.env")


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


def create_knowledge_base(name: str, description: str = None) -> int:
    """
    创建ByteHouse知识库
    
    Args:
        name: 知识库名称
        description: 知识库描述
    
    Returns:
        创建成功的知识库ID
    """
    if not BYTEHOUSE_HOST:
        print("Error: Please set BYTEHOUSE_HOST environment variable", file=sys.stderr)
        sys.exit(1)
    
    url = build_kb_api_url(BYTEHOUSE_HOST, 'knowledge-base')
    auth_token = BYTEHOUSE_PASSWORD if BYTEHOUSE_PASSWORD else ""
    
    headers = {
        "Content-Type": "application/json",
    }
    
    # 添加认证
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    if not name:
        name = get_claw_name()
        # kb_name加上时间戳
        import time
        name += f"_{int(time.time())}"
    
    # 构建请求 payload
    payload = {
        "name": name,
    }

    if description:
        payload["description"] = description

    claw_id = get_claw_id()
    if claw_id:
        payload["tags"] = [{"key": "claw_id", "value": claw_id}]
    
    response = requests.post(url, headers=headers, json=payload, timeout=15)
    response.raise_for_status()
    
    result = response.json()
    kb_id = result.get('id') or (result.get('data', {}).get('id') if isinstance(result.get('data'), dict) else None)

    if not kb_id:
        print(f"Error: Failed to get knowledge base ID from response: {result}", file=sys.stderr)
        sys.exit(1)
    
    return kb_id


def get_claw_name() -> str:
    """从IDENTITY.md获取当前Claw的名字"""
    default_name = "ByteHouse 知识库"
    
    if not os.path.exists(IDENTITY_PATH):
        return default_name
    
    try:
        with open(IDENTITY_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 查找Name字段
        import re
        match = re.search(r'- \*\*Name:\*\*\s*(\w+)', content)
        if match:
            claw_name = match.group(1)
            return f"{claw_name} 知识库"
        else:
            return default_name
    except Exception:
        return default_name


def get_claw_id() -> str:
    """从 .env 获取当前 Claw 的 instance id"""
    default_claw_id = ""

    # Prefer actual environment variable
    claw_id = os.getenv("CLAW_INSTANCE_ID")
    if claw_id:
        return claw_id.strip()

    # If file does not exist, return default
    if not os.path.exists(ENV_PATH):
        return default_claw_id

    try:
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        import re
        match = re.search(r"^CLAW_INSTANCE_ID=(.+)$", content, re.MULTILINE)
        if match:
            return match.group(1).strip()

        return default_claw_id

    except Exception:
        return default_claw_id

def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description='ByteHouse 知识库创建工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python3 create_knowledge_base.py "我的SQL知识库"

环境变量:
  BYTEHOUSE_HOST      - ByteHouse 主机 (如 tenant-xxx-cn-beijing-public.bytehouse.volces.com)
  BYTEHOUSE_PASSWORD  - 密码 (作为 Bearer token)
'''
    )
    
    parser.add_argument('name', nargs='?', help='知识库名称（可选，默认从IDENTITY.md获取）')
    parser.add_argument('-d', '--description', help='知识库描述（可选）')
    
    args = parser.parse_args()
    
    import time
    # 获取知识库名称
    kb_name = args.name if args.name else get_claw_name()  + f"_{int(time.time())}"
    
    try:
        kb_id = create_knowledge_base(kb_name, args.description)
        print(f"{kb_id}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()