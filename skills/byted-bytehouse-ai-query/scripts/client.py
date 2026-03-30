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
ByteHouse 连接客户端 - 通用模块
根据不同实例自动选择合适的连接方式
"""

import os
from typing import Optional

try:
    import clickhouse_connect
except ImportError:
    raise ImportError("clickhouse-connect not installed. Run: pip install clickhouse-connect")


def create_client(
    host: str = None,
    port: str = None,
    user: str = None,
    password: str = None,
    database: str = None
) -> 'clickhouse_connect.Client':
    """
    创建 ByteHouse 连接客户端
    
    自动处理不同实例的连接差异：
    - 8123 端口：需要 secure=True
    - 8443 端口：默认 secure=True
    - password 可能是 "user:password" 格式或纯密码
    
    Args:
        host: ByteHouse 主机
        port: 端口 (默认自动判断)
        user: 用户名
        password: 密码
        database: 数据库名 (可选)
    
    Returns:
        clickhouse_connect 客户端
    """
    # 从环境变量读取
    host = host or os.environ.get('BYTEHOUSE_HOST', '')
    port = port or os.environ.get('BYTEHOUSE_PORT', '')
    user = user or os.environ.get('BYTEHOUSE_USER', '')
    password = password or os.environ.get('BYTEHOUSE_PASSWORD', '')
    database = database or os.environ.get('BYTEHOUSE_DATABASE', '')
    
    if not host:
        raise ValueError("BYTEHOUSE_HOST is required")
    if not user or not password:
        raise ValueError("BYTEHOUSE_USER and BYTEHOUSE_PASSWORD are required")
    
    # 解析端口
    port = int(port) if port else None
    
    # 自动判断端口和加密设置
    if port:
        # 明确指定端口
        secure = port in (8123, 8443, 443)
    else:
        # 自动判断：根据 host 判断
        if 'bytehouse-ce' in host:
            # CE 版本用 8443
            port = 8443
        else:
            # 公有云版本用 8123
            port = 8123
        secure = True
    
    return clickhouse_connect.get_client(
        host=host,
        port=port,
        username=user,
        password=password,
        database=database if database else None,
        secure=secure
    )


def query(client: 'clickhouse_connect.Client', sql: str) -> list:
    """执行查询并返回结果"""
    result = client.query(sql)
    return result.result_rows


def execute(client: 'clickhouse_connect.Client', sql: str):
    """执行查询并打印结果"""
    result = client.query(sql)
    print(result.result_set)


if __name__ == "__main__":
    # 测试连接
    client = create_client()
    result = client.query("SELECT 1 as test")
    print("Connected! Result:", result.result_rows)
    client.close()