#!/usr/bin/env python3
"""
火山引擎 API 搜索工具
用法：python3 find_api.py <搜索关键词> [--limit N]
示例：python3 find_api.py 获取项目列表
      python3 find_api.py ListProjects --limit 5
"""

import sys
import re
import json
import argparse
import urllib.request
import urllib.parse


def strip_em(text):
    return re.sub(r"</?em>", "", text or "")


def search(query, limit=10):
    params = urllib.parse.urlencode({"Query": query, "Channel": "api", "Limit": limit})
    url = f"https://api.volcengine.com/api/common/search/all?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "volcengine-cli-skill/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    return data.get("Result", {}).get("List", [])


def main():
    parser = argparse.ArgumentParser(description="Search Volcengine APIs")
    parser.add_argument("query", nargs="+", help="搜索关键词")
    parser.add_argument("--limit", type=int, default=10, help="返回条数（默认10）")
    parser.add_argument("--json", action="store_true", help="输出原始 JSON")
    args = parser.parse_args()

    query = " ".join(args.query)
    results = search(query, args.limit)

    if not results:
        print("No results found.")
        sys.exit(0)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    # 找出 content 字段的描述
    def get_desc(item):
        for h in item.get("Highlight", []):
            if h.get("Field") == "content":
                return strip_em(h.get("Summary", ""))
        return ""

    # 表格宽度
    rows = []
    for item in results:
        biz = item.get("BizInfo", {})
        rows.append({
            "action":   biz.get("Action", ""),
            "service":  biz.get("ServiceCode", ""),
            "service_cn": biz.get("ServiceCn", ""),
            "version":  biz.get("Version", ""),
            "desc":     get_desc(item),
        })

    col_w = {k: len(k) for k in ("action", "service", "service_cn", "version", "desc")}
    for r in rows:
        for k in col_w:
            col_w[k] = max(col_w[k], len(r[k]))

    def fmt(r):
        return (
            f"  {r['action']:<{col_w['action']}}  "
            f"{r['service']:<{col_w['service']}}  "
            f"{r['service_cn']:<{col_w['service_cn']}}  "
            f"{r['version']:<{col_w['version']}}  "
            f"{r['desc']}"
        )

    header = (
        f"  {'Action':<{col_w['action']}}  "
        f"{'Service':<{col_w['service']}}  "
        f"{'服务名':<{col_w['service_cn']}}  "
        f"{'Version':<{col_w['version']}}  "
        f"{'描述'}"
    )
    sep = "  " + "-" * (sum(col_w.values()) + 8)

    print(f"\nSearch: {query!r}  ({len(rows)} results)\n")
    print(header)
    print(sep)
    for r in rows:
        print(fmt(r))
    print()


if __name__ == "__main__":
    main()
