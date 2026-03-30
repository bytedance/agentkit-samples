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
ByteHouse Execute SQL 脚本
执行 SQL 查询并返回结果

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


def main():
    parser = argparse.ArgumentParser(
        description='执行 ByteHouse SQL 查询',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python3 execute_sql.py "SELECT * FROM tpcds.call_center LIMIT 5"
  python3 execute_sql.py "SELECT count(*) FROM tpcds.store_sales"
  python3 execute_sql.py "SHOW TABLES FROM tpcds"

环境变量:
  BYTEHOUSE_HOST      - ByteHouse 主机
  BYTEHOUSE_PORT     - 端口 (默认自动判断)
  BYTEHOUSE_USER     - 用户名
  BYTEHOUSE_PASSWORD - 密码
  BYTEHOUSE_DATABASE - 默认数据库 (可选)
'''
    )
    
    parser.add_argument('query', nargs='?', help='SQL 查询语句')
    parser.add_argument('--file', '-i', help='从文件读取 SQL 查询')
    
    args = parser.parse_args()
    
    # 获取查询语句
    sql = args.query
    if args.file:
        with open(args.file, 'r') as f:
            sql = f.read().strip()
    
    if not sql:
        print("Error: Please provide a query or use --file", file=sys.stderr)
        sys.exit(1)
    
    try:
        client = create_client()
        result = query(client, sql)
        client.close()
        
        # 打印结果
        for row in result:
            print('\t'.join(str(v) for v in row))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
