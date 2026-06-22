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
ByteHouse 集群诊断工具
直接转发用户的诊断问题到 ByteHouse Matrix Agent API
"""

import os
import sys
import json
import requests

def main():
    if len(sys.argv) < 2:
        print("错误: 请提供诊断问题。用法: python3 diagnostics.py \"你的诊断问题\"")
        sys.exit(1)
        
    question = sys.argv[1]
    host = os.environ.get('BYTEHOUSE_HOST', '').rstrip('/')
    if not host:
        print("错误: 请设置 BYTEHOUSE_HOST 环境变量。")
        sys.exit(1)
        
    # 构建API URL，确保格式正确
    if not host.startswith('http'):
        url = f"https://{host}/matrix/v1/conversation"
    else:
        url = f"{host}/matrix/v1/conversation"
        
    # 如果有认证信息也可以加上，这里主要使用 token 或 user/pass，根据实际情况调整
    token = os.environ.get('BYTEHOUSE_PASSWORD', '')
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream"
    }
    
    if token:
        headers["Authorization"] = f"Bearer {token}"
        
    payload = {
        "input": question,
        "system_hints": "SRE_AGENT_FOLD"
    }
    
    print(f"正在向 {url} 发送诊断问题: {question}...\n")
    print("诊断结果:\n" + "-" * 40)
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=60, stream=True)
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
        
        print("\n" + "-" * 40)
        
    except Exception as e:
        print(f"\n调用诊断API失败: {e}")
        if 'response' in locals() and response is not None:
            print(f"HTTP状态码: {response.status_code}")
            print(f"返回内容: {response.text}")

if __name__ == "__main__":
    main()
