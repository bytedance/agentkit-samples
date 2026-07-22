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

#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "volcengine-python-sdk>=1.0.0",
# ]
# ///
# -*- coding: utf-8 -*-
"""
火山引擎 MongoDB 运维助手调用脚本
用于接收用户命令并调用火山引擎 MongoDB API，返回结果
"""

import os
import sys
import argparse
import json
from typing import Optional, Any, Dict

try:
    import volcenginesdkcore
    from volcenginesdkmongodb.api.mongodb_api import MONGODBApi
    from volcenginesdkmongodb import models
except ImportError as e:
    print(
        "错误: 缺少必要的依赖包。请先安装: pip install 'volcengine-python-sdk'",
        file=sys.stderr,
    )
    print(f"详细错误: {e}", file=sys.stderr)
    sys.exit(1)


class MongoDBClient:
    """火山引擎 MongoDB 客户端封装"""

    def __init__(self, region: str = "cn-beijing", endpoint: Optional[str] = None):
        """
        初始化 MongoDB 客户端

        Args:
            region: 地域 ID，默认为 cn-beijing
            endpoint: API 端点（可选）
        """
        self.region = region
        self.endpoint = endpoint
        self.client = self._create_client()

    def _create_client(self) -> MONGODBApi:
        """创建火山引擎 MongoDB 客户端"""
        access_key = os.getenv("VOLCENGINE_ACCESS_KEY")
        secret_key = os.getenv("VOLCENGINE_SECRET_KEY")

        if not access_key or not secret_key:
            raise ValueError(
                "未找到火山引擎访问凭证。请设置环境变量:\n"
                "  VOLCENGINE_ACCESS_KEY\n"
                "  VOLCENGINE_SECRET_KEY"
            )

        configuration = volcenginesdkcore.Configuration()
        configuration.ak = access_key
        configuration.sk = secret_key
        configuration.region = self.region
        if self.endpoint:
            configuration.host = self.endpoint

        return MONGODBApi(
            volcenginesdkcore.ApiClient(configuration, "X-Mongomgr-Source", "mcp_skill")
        )

    def _to_dict(self, obj: Any) -> Any:
        """将 SDK 响应对象转换为字典"""
        if obj is None:
            return None
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        if isinstance(obj, list):
            return [self._to_dict(item) for item in obj]
        if isinstance(obj, dict):
            return {k: self._to_dict(v) for k, v in obj.items()}
        return obj

    def list_instances(
        self,
        page_number: int = 1,
        instance_id: Optional[str] = None,
        instance_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """查询 MongoDB 实例列表"""
        req_params = {
            "page_number": page_number,
            "page_size": 10,
        }
        if instance_id:
            req_params["instance_id"] = instance_id
        if instance_name:
            req_params["instance_name"] = instance_name

        resp = self.client.describe_db_instances(
            models.DescribeDBInstancesRequest(**req_params)
        )
        return self._to_dict(resp)

    def describe_instance(self, instance_id: str) -> Dict[str, Any]:
        """查询指定实例详情"""
        resp = self.client.describe_db_instance_detail(
            models.DescribeDBInstanceDetailRequest(instance_id=instance_id)
        )
        return self._to_dict(resp)

    def list_backups(
        self,
        instance_id: str,
        page_number: int = 1,
    ) -> Dict[str, Any]:
        """查询实例备份列表"""
        req_params = {
            "instance_id": instance_id,
            "page_number": page_number,
            "page_size": 10,
        }

        resp = self.client.describe_backups(
            models.DescribeBackupsRequest(**req_params)
        )
        return self._to_dict(resp)

    def list_parameters(
        self,
        instance_id: str,
    ) -> Dict[str, Any]:
        """查询实例的参数配置"""
        req_params = {"instance_id": instance_id}

        resp = self.client.describe_db_instance_parameters(
            models.DescribeDBInstanceParametersRequest(**req_params)
        )
        return self._to_dict(resp)

def format_output(data: Any, output_format: str = "json") -> str:
    """格式化输出"""
    if output_format == "json":
        return json.dumps(data, indent=2, ensure_ascii=False, default=str)
    else:
        return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="火山引擎 MongoDB 运维助手命令行工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 查询实例列表
  python call_mongodb.py list-instances

  # 查询指定实例详情
  python call_mongodb.py describe-instance --instance-id mongo-xxx

  # 查询实例备份列表
  python call_mongodb.py list-backups --instance-id mongo-xxx

  # 查询实例参数
  python call_mongodb.py list-parameters --instance-id mongo-xxx
        """,
    )

    # 子命令
    subparsers = parser.add_subparsers(dest="action", help="操作类型")

    # list-instances
    list_instances_parser = subparsers.add_parser(
        "list-instances", help="查询 MongoDB 实例列表"
    )
    list_instances_parser.add_argument(
        "--instance-id", "-i", dest="instance_id", help="实例 ID（可选，用于过滤）"
    )
    list_instances_parser.add_argument(
        "--instance-name", dest="instance_name", help="实例名称（可选，用于过滤）"
    )

    # describe-instance
    describe_instance_parser = subparsers.add_parser(
        "describe-instance", help="查询指定实例详情"
    )
    describe_instance_parser.add_argument(
        "--instance-id", "-i", dest="instance_id", required=True, help="实例 ID"
    )

    # list-backups
    list_backups_parser = subparsers.add_parser(
        "list-backups", help="查询实例备份列表"
    )
    list_backups_parser.add_argument(
        "--instance-id", "-i", dest="instance_id", required=True, help="实例 ID"
    )

    # list-parameters
    list_parameters_parser = subparsers.add_parser(
        "list-parameters", help="查询实例的参数配置"
    )
    list_parameters_parser.add_argument(
        "--instance-id", "-i", dest="instance_id", required=True, help="实例 ID"
    )

    # 通用参数
    parser.add_argument(
        "--region",
        "-r",
        dest="region",
        default=os.getenv("VOLCENGINE_REGION", "cn-beijing"),
        help="火山引擎地域 ID（默认: cn-beijing）",
    )
    parser.add_argument("--endpoint", dest="endpoint", help="API 端点（可选）")
    parser.add_argument(
        "--page-number",
        dest="page_number",
        type=int,
        default=1,
        help="分页页码（默认: 1）",
    )
    parser.add_argument(
        "--page-size",
        dest="page_size",
        type=int,
        default=10,
        help="每页记录数（默认: 10）",
    )
    parser.add_argument(
        "--output",
        "-o",
        dest="output",
        default="json",
        choices=["json", "table"],
        help="输出格式（默认: json）",
    )

    args = parser.parse_args()

    if not args.action:
        parser.print_help()
        sys.exit(1)

    # 输出操作信息到 stderr
    print(f"[操作] {args.action}", file=sys.stderr)
    print(f"[地域] {args.region}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    try:
        client = MongoDBClient(region=args.region, endpoint=args.endpoint)

        result = None

        if args.action == "list-instances":
            result = client.list_instances(
                page_number=args.page_number,
                instance_id=getattr(args, "instance_id", None),
                instance_name=getattr(args, "instance_name", None),
            )
        elif args.action == "describe-instance":
            result = client.describe_instance(instance_id=args.instance_id)
        elif args.action == "list-backups":
            result = client.list_backups(
                instance_id=args.instance_id,
                page_number=args.page_number,
            )
        elif args.action == "list-parameters":
            result = client.list_parameters(
                instance_id=args.instance_id,
            )
        else:
            print(f"未知操作: {args.action}", file=sys.stderr)
            sys.exit(1)

        print("[查询结果]", file=sys.stderr)
        print(format_output(result, args.output))

    except ValueError as e:
        print(f"\n配置错误: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n调用 MongoDB API 时出错: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
