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
ByteHouse List Tables 脚本
列出指定数据库中的所有表

依赖: clickhouse-connect
安装: pip install clickhouse-connect

环境变量:
  BYTEHOUSE_HOST      - ByteHouse 主机地址
  BYTEHOUSE_PORT     - 端口 (默认自动判断)
  BYTEHOUSE_USER     - 用户名
  BYTEHOUSE_PASSWORD - 密码
  BYTEHOUSE_DATABASE - 默认数据库 (可选)
"""

import sys
import argparse
from client import create_client, query


def list_databases():
    """列出所有数据库"""
    client = create_client()
    result = query(client, "SHOW DATABASES")
    client.close()
    return [row[0] for row in result]


def list_tables(database: str):
    """列出指定数据库中的所有表"""
    client = create_client()
    # 用系统表查询更稳定
    result = query(client, f"SELECT name FROM system.tables WHERE database = '{database}' LIMIT 100")
    client.close()
    return [row[0] for row in result]


def main():
    parser = argparse.ArgumentParser(description='列出 ByteHouse 数据库中的表')
    parser.add_argument('--database', '-d', help='数据库名')
    parser.add_argument('--databases', '-D', action='store_true', help='列出所有数据库')
    
    args = parser.parse_args()
    
    try:
        if args.databases:
            dbs = list_databases()
            print("Databases:")
            for db in dbs:
                print(f"  - {db}")
        else:
            database = args.database
            if not database:
                print("Error: Please specify --database", file=sys.stderr)
                sys.exit(1)
            tables = list_tables(database)
            print(f"Tables in '{database}':")
            for table in tables:
                print(f"  - {table}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()