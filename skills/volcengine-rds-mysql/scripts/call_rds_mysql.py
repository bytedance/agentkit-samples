#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "volcengine-python-sdk[rdsmysqlv2,vpc]>=1.0.0",
# ]
# ///
# -*- coding: utf-8 -*-
"""
火山引擎 RDS MySQL 运维助手调用脚本
用于接收用户命令并调用火山引擎 RDS MySQL API，返回结果
"""

import os
import sys
import argparse
import json
from typing import Optional, Any, Dict

try:
    import volcenginesdkcore
    from volcenginesdkrdsmysqlv2.api.rds_mysql_v2_api import RDSMYSQLV2Api
    from volcenginesdkrdsmysqlv2 import models
    from volcenginesdkvpc.api.vpc_api import VPCApi
    from volcenginesdkvpc.models import (
        DescribeVpcsRequest,
        DescribeSubnetsRequest,
    )
except ImportError as e:
    print(
        "错误: 缺少必要的依赖包。请先安装: pip install 'volcengine-python-sdk[rdsmysqlv2,vpc]'",
        file=sys.stderr,
    )
    print(f"详细错误: {e}", file=sys.stderr)
    sys.exit(1)


class RDSMySQLClient:
    """火山引擎 RDS MySQL 客户端封装"""

    def __init__(self, region: str = "cn-beijing", endpoint: Optional[str] = None):
        """
        初始化 RDS MySQL 客户端

        Args:
            region: 地域 ID，默认为 cn-beijing
            endpoint: API 端点（可选）
        """
        self.region = region
        self.endpoint = endpoint
        self.client = self._create_client()
        self.vpc_client = self._create_vpc_client()

    def _create_client(self) -> RDSMYSQLV2Api:
        """创建火山引擎 RDS MySQL 客户端"""
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

        return RDSMYSQLV2Api(
            volcenginesdkcore.ApiClient(configuration, "X-Rdsmgr-Source", "mcp_skill")
        )

    def _create_vpc_client(self) -> VPCApi:
        """创建火山引擎 VPC 客户端"""
        access_key = os.getenv("VOLCENGINE_ACCESS_KEY")
        secret_key = os.getenv("VOLCENGINE_SECRET_KEY")

        configuration = volcenginesdkcore.Configuration()
        configuration.ak = access_key
        configuration.sk = secret_key
        configuration.region = self.region

        return VPCApi(volcenginesdkcore.ApiClient(configuration))

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
        page_size: int = 10,
        instance_id: Optional[str] = None,
        instance_name: Optional[str] = None,
        instance_status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """查询 RDS MySQL 实例列表"""
        req_params = {
            "page_number": page_number,
            "page_size": page_size,
        }
        if instance_id:
            req_params["instance_id"] = instance_id
        if instance_name:
            req_params["instance_name"] = instance_name
        if instance_status:
            req_params["instance_status"] = instance_status

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

    def list_databases(
        self,
        instance_id: str,
        db_name: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 10,
    ) -> Dict[str, Any]:
        """查询实例的数据库列表"""
        req_params = {
            "instance_id": instance_id,
            "page_number": page_number,
            "page_size": page_size,
        }
        if db_name:
            req_params["db_name"] = db_name

        resp = self.client.describe_databases(
            models.DescribeDatabasesRequest(**req_params)
        )
        return self._to_dict(resp)

    def list_accounts(
        self,
        instance_id: str,
        account_name: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 10,
    ) -> Dict[str, Any]:
        """查询实例的账号列表"""
        req_params = {
            "instance_id": instance_id,
            "page_number": page_number,
            "page_size": page_size,
        }
        if account_name:
            req_params["account_name"] = account_name

        resp = self.client.describe_db_accounts(
            models.DescribeDBAccountsRequest(**req_params)
        )
        return self._to_dict(resp)

    def list_parameters(
        self,
        instance_id: str,
        parameter_name: Optional[str] = None,
        node_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """查询实例的参数配置"""
        req_params = {"instance_id": instance_id}
        if parameter_name:
            req_params["parameter_name"] = parameter_name
        if node_id:
            req_params["node_id"] = node_id

        resp = self.client.describe_db_instance_parameters(
            models.DescribeDBInstanceParametersRequest(**req_params)
        )
        return self._to_dict(resp)

    def list_parameter_templates(
        self,
        template_type: str = "Mysql",
        template_type_version: Optional[str] = None,
        template_source: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """查询参数模板列表"""
        req_params = {
            "template_type": template_type,
            "limit": limit,
            "offset": offset,
        }
        if template_type_version:
            req_params["template_type_version"] = template_type_version
        if template_source:
            req_params["template_source"] = template_source

        resp = self.client.list_parameter_templates(
            models.ListParameterTemplatesRequest(**req_params)
        )
        return self._to_dict(resp)

    def describe_parameter_template(self, template_id: str) -> Dict[str, Any]:
        """查询参数模板详情"""
        resp = self.client.describe_parameter_template(
            models.DescribeParameterTemplateRequest(template_id=template_id)
        )
        return self._to_dict(resp)

    def list_vpcs(self, page_number: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """查询 VPC 列表"""
        resp = self.vpc_client.describe_vpcs(
            DescribeVpcsRequest(page_number=page_number, page_size=page_size)
        )
        return self._to_dict(resp)

    def list_subnets(
        self, vpc_id: str, zone_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """查询子网列表"""
        req_params = {"vpc_id": vpc_id}
        if zone_id:
            req_params["zone_id"] = zone_id

        resp = self.vpc_client.describe_subnets(DescribeSubnetsRequest(**req_params))
        return self._to_dict(resp)

    def get_price(
        self,
        node_spec: str = "rds.mysql.1c2g",
        storage_space: int = 20,
        storage_type: str = "LocalSSD",
        charge_type: str = "PostPaid",
        zone_id: str = "cn-beijing-a",
    ) -> Dict[str, Any]:
        """查询实例价格"""
        node_info = [
            {"NodeType": "Primary", "ZoneId": zone_id, "NodeSpec": node_spec},
            {"NodeType": "Secondary", "ZoneId": zone_id, "NodeSpec": node_spec},
        ]

        req_params = {
            "node_info": node_info,
            "storage_type": storage_type,
            "storage_space": storage_space,
            "charge_type": charge_type,
        }

        resp = self.client.describe_db_instance_price_detail(
            models.DescribeDBInstancePriceDetailRequest(**req_params)
        )
        return self._to_dict(resp)


def format_output(data: Any, output_format: str = "json") -> str:
    """格式化输出"""
    if output_format == "json":
        return json.dumps(data, indent=2, ensure_ascii=False, default=str)
    else:
        # 简单的表格格式
        return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="火山引擎 RDS MySQL 运维助手命令行工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 查询实例列表
  python call_rds_mysql.py list-instances

  # 查询指定实例详情
  python call_rds_mysql.py describe-instance --instance-id mysql-xxx

  # 查询实例的数据库列表
  python call_rds_mysql.py list-databases --instance-id mysql-xxx

  # 查询实例的账号列表
  python call_rds_mysql.py list-accounts --instance-id mysql-xxx

  # 查询实例参数
  python call_rds_mysql.py list-parameters --instance-id mysql-xxx

  # 查询 VPC 列表
  python call_rds_mysql.py list-vpcs

  # 查询子网列表
  python call_rds_mysql.py list-subnets --vpc-id vpc-xxx --zone-id cn-beijing-a
        """,
    )

    # 子命令
    subparsers = parser.add_subparsers(dest="action", help="操作类型")

    # list-instances
    list_instances_parser = subparsers.add_parser(
        "list-instances", help="查询 RDS MySQL 实例列表"
    )
    list_instances_parser.add_argument(
        "--instance-id", "-i", dest="instance_id", help="实例 ID（可选，用于过滤）"
    )
    list_instances_parser.add_argument(
        "--instance-name", dest="instance_name", help="实例名称（可选，用于过滤）"
    )
    list_instances_parser.add_argument(
        "--instance-status", dest="instance_status", help="实例状态（可选，用于过滤）"
    )

    # describe-instance
    describe_instance_parser = subparsers.add_parser(
        "describe-instance", help="查询指定实例详情"
    )
    describe_instance_parser.add_argument(
        "--instance-id", "-i", dest="instance_id", required=True, help="实例 ID"
    )

    # list-databases
    list_databases_parser = subparsers.add_parser(
        "list-databases", help="查询实例的数据库列表"
    )
    list_databases_parser.add_argument(
        "--instance-id", "-i", dest="instance_id", required=True, help="实例 ID"
    )
    list_databases_parser.add_argument(
        "--db-name", dest="db_name", help="数据库名称（可选，用于过滤）"
    )

    # list-accounts
    list_accounts_parser = subparsers.add_parser(
        "list-accounts", help="查询实例的账号列表"
    )
    list_accounts_parser.add_argument(
        "--instance-id", "-i", dest="instance_id", required=True, help="实例 ID"
    )
    list_accounts_parser.add_argument(
        "--account-name", dest="account_name", help="账号名称（可选，用于过滤）"
    )

    # list-parameters
    list_parameters_parser = subparsers.add_parser(
        "list-parameters", help="查询实例的参数配置"
    )
    list_parameters_parser.add_argument(
        "--instance-id", "-i", dest="instance_id", required=True, help="实例 ID"
    )
    list_parameters_parser.add_argument(
        "--parameter-name", dest="parameter_name", help="参数名称（可选）"
    )
    list_parameters_parser.add_argument(
        "--node-id", dest="node_id", help="节点 ID（可选）"
    )

    # list-parameter-templates
    list_templates_parser = subparsers.add_parser(
        "list-parameter-templates", help="查询参数模板列表"
    )
    list_templates_parser.add_argument(
        "--template-type-version",
        dest="template_type_version",
        help="数据库版本（如 MySQL_5_7、MySQL_8_0）",
    )
    list_templates_parser.add_argument(
        "--template-source",
        dest="template_source",
        help="模板来源（System 或 User）",
    )

    # describe-parameter-template
    describe_template_parser = subparsers.add_parser(
        "describe-parameter-template", help="查询参数模板详情"
    )
    describe_template_parser.add_argument(
        "--template-id", dest="template_id", required=True, help="参数模板 ID"
    )

    # list-vpcs
    subparsers.add_parser("list-vpcs", help="查询 VPC 列表")

    # list-subnets
    list_subnets_parser = subparsers.add_parser("list-subnets", help="查询子网列表")
    list_subnets_parser.add_argument(
        "--vpc-id", dest="vpc_id", required=True, help="VPC ID"
    )
    list_subnets_parser.add_argument(
        "--zone-id", dest="zone_id", help="可用区 ID（可选）"
    )

    # get-price
    get_price_parser = subparsers.add_parser("get-price", help="查询实例价格")
    get_price_parser.add_argument(
        "--node-spec",
        dest="node_spec",
        default="rds.mysql.1c2g",
        help="节点规格（默认: rds.mysql.1c2g）",
    )
    get_price_parser.add_argument(
        "--storage-space",
        dest="storage_space",
        type=int,
        default=20,
        help="存储空间 GB（默认: 20）",
    )
    get_price_parser.add_argument(
        "--charge-type",
        dest="charge_type",
        default="PostPaid",
        help="计费类型（默认: PostPaid）",
    )
    get_price_parser.add_argument(
        "--zone-id",
        dest="zone_id",
        default="cn-beijing-a",
        help="可用区（默认: cn-beijing-a）",
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
        client = RDSMySQLClient(region=args.region, endpoint=args.endpoint)

        result = None

        if args.action == "list-instances":
            result = client.list_instances(
                page_number=args.page_number,
                page_size=args.page_size,
                instance_id=getattr(args, "instance_id", None),
                instance_name=getattr(args, "instance_name", None),
                instance_status=getattr(args, "instance_status", None),
            )
        elif args.action == "describe-instance":
            result = client.describe_instance(instance_id=args.instance_id)
        elif args.action == "list-databases":
            result = client.list_databases(
                instance_id=args.instance_id,
                db_name=getattr(args, "db_name", None),
                page_number=args.page_number,
                page_size=args.page_size,
            )
        elif args.action == "list-accounts":
            result = client.list_accounts(
                instance_id=args.instance_id,
                account_name=getattr(args, "account_name", None),
                page_number=args.page_number,
                page_size=args.page_size,
            )
        elif args.action == "list-parameters":
            result = client.list_parameters(
                instance_id=args.instance_id,
                parameter_name=getattr(args, "parameter_name", None),
                node_id=getattr(args, "node_id", None),
            )
        elif args.action == "list-parameter-templates":
            result = client.list_parameter_templates(
                template_type_version=getattr(args, "template_type_version", None),
                template_source=getattr(args, "template_source", None),
            )
        elif args.action == "describe-parameter-template":
            result = client.describe_parameter_template(template_id=args.template_id)
        elif args.action == "list-vpcs":
            result = client.list_vpcs(
                page_number=args.page_number, page_size=args.page_size
            )
        elif args.action == "list-subnets":
            result = client.list_subnets(
                vpc_id=args.vpc_id, zone_id=getattr(args, "zone_id", None)
            )
        elif args.action == "get-price":
            result = client.get_price(
                node_spec=args.node_spec,
                storage_space=args.storage_space,
                charge_type=args.charge_type,
                zone_id=args.zone_id,
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
        print(f"\n调用 RDS MySQL API 时出错: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
