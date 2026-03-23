#!/usr/bin/env python3
"""Describe datasource tool — retrieves metadata for available data sources.

Usage:
  python3 scripts/describe_datasource.py --datasource-id all
  python3 scripts/describe_datasource.py --datasource-id enterprise_basic_wide
"""

import argparse
import json
import sys

from mcp_gateway_client import (
    DEFAULT_MCP_GATEWAY_URL,
    call_mcp_tool,
    load_credentials,
    pretty_print_mcp_result,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="查询数据源元数据（维度、字段类型、可用过滤操作符）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 列出所有数据源摘要
  python3 scripts/describe_datasource.py --datasource-id all

  # 查看企业基本信息宽表的完整字段定义
  python3 scripts/describe_datasource.py --datasource-id enterprise_basic_wide

  # 查看产业链企业信息字段
  python3 scripts/describe_datasource.py --datasource-id industry_chain_company_info
""",
    )

    parser.add_argument(
        "--datasource-id",
        default="all",
        help="数据源 ID，或 'all' 列出全部（默认: all）",
    )
    parser.add_argument(
        "--locale",
        default="zh-CN",
        help="字段描述语言（默认: zh-CN）",
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_MCP_GATEWAY_URL,
        help="MCP Gateway URL",
    )
    parser.add_argument(
        "--access-key",
        default=None,
        help="VOLCENGINE_ACCESS_KEY（可选，覆盖环境变量）",
    )
    parser.add_argument(
        "--secret-key",
        default=None,
        help="VOLCENGINE_SECRET_KEY（可选，覆盖环境变量）",
    )
    parser.add_argument(
        "--raw-response",
        action="store_true",
        help="输出完整 MCP JSON-RPC 响应",
    )

    args = parser.parse_args()

    try:
        ak, sk = load_credentials(args.access_key, args.secret_key)
        resp = call_mcp_tool(
            url=args.url,
            access_key=ak,
            secret_key=sk,
            tool_name="describe_datasource",
            arguments={"datasource_id": args.datasource_id, "locale": args.locale},
        )

        if args.raw_response:
            print(json.dumps(resp, ensure_ascii=False, indent=2))
        else:
            pretty_print_mcp_result(resp)

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
