#!/usr/bin/env python3
"""Query datasource tool — retrieves actual data from a data source.

Usage:
  python3 scripts/query_datasource.py --datasource-id enterprise_basic_wide --filters 'company_name:like:字节跳动'
  python3 scripts/query_datasource.py --datasource-id industry_chain_company_info --filters 'chain_name:like:新能源' --aggregation 'count'
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
        description="查询数据源数据（支持过滤、聚合、分组、排序、分页）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 模糊搜索企业
  python3 scripts/query_datasource.py \\
    --datasource-id enterprise_basic_wide \\
    --filters 'company_name:like:字节跳动'

  # 聚合统计
  python3 scripts/query_datasource.py \\
    --datasource-id industry_chain_company_info \\
    --filters 'chain_name:like:新能源汽车' \\
    --aggregation 'count'

  # 分组统计
  python3 scripts/query_datasource.py \\
    --datasource-id industry_chain_company_info \\
    --filters 'chain_name:like:新能源汽车' \\
    --group-by 'base_name' \\
    --aggregation 'company_id:count'

  # 按证券编码查上市公司
  python3 scripts/query_datasource.py \\
    --datasource-id stock_company_brief \\
    --filters 'code:eq:000001'
""",
    )

    parser.add_argument("--datasource-id", required=True, help="数据源 ID（必填）")
    parser.add_argument(
        "--select-fields",
        default=None,
        help="逗号分隔的返回字段（可选，服务端默认返回所有非屏蔽维度字段）",
    )
    parser.add_argument(
        "--filters",
        default=None,
        help="过滤条件，格式: 'field:op:value'，多个用 ';' 分隔",
    )
    parser.add_argument(
        "--aggregation",
        default=None,
        help="聚合操作: 'count' | 'field:count' | 'field:distinct' | 'field:sum/avg/max/min'",
    )
    parser.add_argument(
        "--group-by",
        default=None,
        help="分组字段，逗号分隔（需配合 --aggregation 使用）",
    )
    parser.add_argument("--sort-field", default=None, help="排序字段名")
    parser.add_argument(
        "--sort-order",
        default="desc",
        choices=["asc", "desc"],
        help="排序方向（默认: desc）",
    )
    parser.add_argument("--page", type=int, default=1, help="页码，从 1 开始（默认: 1）")

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

    if args.page < 1:
        raise SystemExit("--page must be >= 1")

    try:
        ak, sk = load_credentials(args.access_key, args.secret_key)
        arguments = {
            "datasource_id": args.datasource_id,
            "select_fields": args.select_fields,
            "filters": args.filters,
            "aggregation": args.aggregation,
            "group_by": args.group_by,
            "sort_field": args.sort_field,
            "sort_order": args.sort_order,
            "page": args.page,
        }
        # Remove None values to avoid sending unnecessary parameters
        arguments = {k: v for k, v in arguments.items() if v is not None}

        resp = call_mcp_tool(
            url=args.url,
            access_key=ak,
            secret_key=sk,
            tool_name="query_datasource",
            arguments=arguments,
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
