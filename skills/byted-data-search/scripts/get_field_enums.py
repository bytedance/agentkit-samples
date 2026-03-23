#!/usr/bin/env python3
"""Get field enum values — quickly discover the distinct values a field can take.

Returns up to 200 distinct values for a given field in a datasource,
sorted by frequency (most common first). This is essential when you need
to construct exact-match filters (eq/in) but aren't sure what values
the field actually contains.

Usage:
  python3 scripts/get_field_enums.py --datasource-id enterprise_basic_wide --field reg_status
  python3 scripts/get_field_enums.py --datasource-id industry_chain_company_info --field base_name --filters 'chain_name:like:新能源汽车'
"""

import argparse
import json
import sys

from mcp_gateway_client import (
    DEFAULT_MCP_GATEWAY_URL,
    call_mcp_tool,
    extract_tool_text,
    load_credentials,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="查询某个数据源中指定字段的枚举值（最多返回 200 个不同取值，按出现频次降序排列）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 查看企业状态有哪些取值
  python3 scripts/get_field_enums.py \\
    --datasource-id enterprise_basic_wide --field reg_status

  # 查看某产业链下企业的省份分布
  python3 scripts/get_field_enums.py \\
    --datasource-id industry_chain_company_info --field base_name \\
    --filters 'chain_name:like:新能源汽车'

  # 查看产业链区域指标中 region_level 有哪些取值
  python3 scripts/get_field_enums.py \\
    --datasource-id industry_chain_node_region_metric --field region_level
""",
    )

    parser.add_argument(
        "--datasource-id",
        required=True,
        help="数据源 ID（必填）",
    )
    parser.add_argument(
        "--field",
        required=True,
        help="要查询枚举值的字段名（必填）",
    )
    parser.add_argument(
        "--filters",
        default=None,
        help="可选的前置过滤条件，格式同 query_datasource（如 'chain_name:like:新能源汽车'）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="最多返回的枚举值数量（默认: 200，上限: 300）",
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

    args = parser.parse_args()

    # Cap limit at 50 (server max page_size)
    limit = min(args.limit, 300)

    try:
        ak, sk = load_credentials(args.access_key, args.secret_key)

        # Use group_by + aggregation to get distinct values via terms aggregation.
        # The server translates group_by into an ES terms aggregation whose
        # bucket size equals page_size, so we set page_size = limit.
        arguments = {
            "datasource_id": args.datasource_id,
            "group_by": args.field,
            "aggregation": f"{args.field}:count",
            "page_size": limit,
        }
        if args.filters:
            arguments["filters"] = args.filters

        resp = call_mcp_tool(
            url=args.url,
            access_key=ak,
            secret_key=sk,
            tool_name="query_datasource",
            arguments=arguments,
        )

        # --- Parse response ---
        tool_text = extract_tool_text(resp)
        if tool_text is None:
            # MCP-level error
            print(json.dumps(resp, ensure_ascii=False, indent=2), file=sys.stderr)
            sys.exit(1)

        parsed = json.loads(tool_text)

        # Check for server-side error
        if "error" in parsed:
            err = parsed["error"]
            print(f"Error [{err.get('code', 'UNKNOWN')}]: {err.get('message', '')}", file=sys.stderr)
            if "suggestion" in err:
                print(f"Suggestion: {err['suggestion']}", file=sys.stderr)
            sys.exit(1)

        # Extract enum values from aggregation_result
        agg_result = parsed.get("aggregation_result", [])
        if not agg_result:
            print(f"字段 '{args.field}' 在数据源 '{args.datasource_id}' 中未找到任何取值。", file=sys.stderr)
            print(f"请确认字段名是否正确（可运行: python3 scripts/describe_datasource.py --datasource-id {args.datasource_id}）", file=sys.stderr)
            sys.exit(0)

        # Each bucket in agg_result is a dict like:
        #   { "<field>": "<value>", "doc_count": 123, "<field>_count": 123 }
        values = []
        for bucket in agg_result:
            val = bucket.get(args.field)
            count = bucket.get("doc_count", 0)
            if val is not None:
                values.append({"value": val, "count": count})

        # Output
        print(f"数据源: {args.datasource_id}")
        print(f"字段:   {args.field}")
        if args.filters:
            print(f"过滤:   {args.filters}")
        print(f"共找到 {len(values)} 个不同取值（最多显示 {limit} 个）:\n")

        for i, item in enumerate(values, 1):
            print(f"  {i:>2}. {item['value']}  ({item['count']} 条)")

        # Also output a machine-readable JSON line for programmatic consumption
        print(f"\n[JSON] {json.dumps([v['value'] for v in values], ensure_ascii=False)}")

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
