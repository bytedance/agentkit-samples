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
ByteHouse Text2SQL API 客户端
用于调用 ByteHouse 的 text2sql 接口，将自然语言转换为 SQL 查询

配置方式：设置以下环境变量
- BYTEHOUSE_HOST: ByteHouse 主机地址 (如 tenant-xxx-cn-beijing-public.bytehouse.volces.com)
- BYTEHOUSE_PASSWORD: 密码 (用作 Bearer token)

或通过 --config 参数传入自定义配置：
- reasoningModel: 自定义模型ID
- reasoningAPIKey: 自定义 API Key
- url: 自定义 API URL
"""

import os
import requests
import json
import re
import sys
import argparse

# 从环境变量读取默认配置
BYTEHOUSE_HOST = os.environ.get('BYTEHOUSE_HOST', '')
BYTEHOUSE_PASSWORD = os.environ.get('BYTEHOUSE_PASSWORD', '')


def build_text2sql_url(host: str) -> str:
    """构建 Text2SQL API URL"""
    if not host:
        print("Error: BYTEHOUSE_HOST environment variable is required", file=sys.stderr)
        sys.exit(1)
    
    # 处理 host - 可能是 host:port 格式
    if host.startswith('http'):
        base_url = host.rstrip('/')
    else:
        base_url = f"https://{host}"
    
    return f"{base_url}/matrix/v1/conversation"


def call_text2sql(
    natural_language: str, 
    tables: list, 
    system_hints: str = "TEXT2SQL",
    config: dict = None
) -> str:
    """
    调用 ByteHouse Text2SQL 接口，将自然语言转换为 SQL
    
    Args:
        natural_language: 自然语言描述的查询需求
        tables: 要查询的表名列表，如 ["bytehouse.query_history"]
        system_hints: 系统提示词，默认为 "TEXT2SQL"
        config: 可选的配置 dict，支持:
            - reasoningModel: 自定义模型ID
            - reasoningAPIKey: 自定义 API Key
            - url: 自定义 API URL
    
    Returns:
        转换后的 SQL 语句
    """
    # 决定使用哪个配置：用户提供的 config > 环境变量
    if config:
        # 使用用户提供的自定义配置
        base_url = config.get('url', '')
        auth_token = config.get('reasoningAPIKey', '')
        reasoning_model = config.get('reasoningModel', '')
        
        if not base_url:
            print("Error: config.url is required when using custom config", file=sys.stderr)
            sys.exit(1)
        
        # 用户提供的 URL 可能已经包含完整路径，直接使用
        # 如果 URL 已经包含任何 path（如 /api/v3），则不再追加
        if '/' in base_url.split('://')[-1]:
            url = base_url.rstrip('/')
        else:
            url = f"{base_url.rstrip('/')}/matrix/v1/conversation"
    else:
        # 使用环境变量中的默认配置
        if not BYTEHOUSE_HOST:
            print("Error: Please set BYTEHOUSE_HOST environment variable or provide --config", file=sys.stderr)
            sys.exit(1)
        
        url = build_text2sql_url(BYTEHOUSE_HOST)
        auth_token = BYTEHOUSE_PASSWORD if BYTEHOUSE_PASSWORD else ""
        reasoning_model = ""
    
    headers = {
        "Content-Type": "application/json",
    }
    
    # 添加认证
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    
    # 构建请求 payload
    payload = {
        "systemHints": system_hints,
        "input": natural_language,
        "knowledgeBaseIDsString": ["*"],
        "tables": tables
    }
    
    # 如果用户指定了 reasoningModel，添加到 payload
    if reasoning_model:
        payload["config"] = {
            "reasoningModel": reasoning_model
        }
    
    # 使用流式请求
    response = requests.post(url, headers=headers, json=payload, stream=True)
    response.raise_for_status()
    
    # 收集所有内容片段
    full_content = ""
    
    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data: '):
                data_str = line[6:]  # 去掉 'data: ' 前缀
                try:
                    data = json.loads(data_str)
                    event_type = data.get('event_type')
                    
                    if event_type == 'DELTA':
                        event_data = json.loads(data.get('event_data', '{}'))
                        message = event_data.get('message', {})
                        content = message.get('content', '')
                        full_content += content
                    elif event_type == 'DONE':
                        break
                except json.JSONDecodeError:
                    continue
    
    # 清理和提取 SQL
    sql = extract_sql(full_content)
    return sql


def extract_sql(content: str) -> str:
    """
    从内容中提取 SQL 语句
    移除 markdown 代码块标记，清理空白字符
    """
    if not content:
        return ""
    
    # 移除 markdown 代码块标记
    sql = content.strip()
    sql = re.sub(r'^```\w*\n', '', sql)
    sql = re.sub(r'\n```$', '', sql)
    
    # 规范化空白字符
    sql = re.sub(r'\s+', ' ', sql)
    sql = sql.strip()
    
    return sql


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description='ByteHouse Text2SQL - 将自然语言转换为 SQL 查询',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python3 text2sql.py "get count of queries" "bytehouse.query_history"
  python3 text2sql.py "查看最近10条记录" "bytehouse.query_history" --config '{"reasoningModel": "ep-xxx", "reasoningAPIKey": "xxx", "url": "https://xxx"}'

环境变量:
  BYTEHOUSE_HOST      - ByteHouse 主机 (如 tenant-xxx-cn-beijing-public.bytehouse.volces.com)
  BYTEHOUSE_PASSWORD  - 密码 (作为 Bearer token)

自定义 Config (通过 --config 参数):
  reasoningModel  - 自定义模型ID
  reasoningAPIKey - 自定义 API Key
  url            - 自定义 API URL
'''
    )
    
    parser.add_argument('query', help='自然语言查询')
    parser.add_argument('tables', nargs='+', help='要查询的表名列表')
    parser.add_argument('--config', type=str, help='JSON 格式的配置，包含 reasoningModel, reasoningAPIKey, url')
    parser.add_argument('--system-hints', type=str, default='TEXT2SQL', help='系统提示词 (默认: TEXT2SQL)')
    
    args = parser.parse_args()
    
    # 解析 config 参数
    config = None
    if args.config:
        try:
            config = json.loads(args.config)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in --config: {e}", file=sys.stderr)
            sys.exit(1)
    
    # 检查必要配置
    if not config and not BYTEHOUSE_HOST:
        print("Error: Please set BYTEHOUSE_HOST environment variable or provide --config", file=sys.stderr)
        sys.exit(1)
    
    try:
        sql = call_text2sql(args.query, args.tables, args.system_hints, config)
        print(sql)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
