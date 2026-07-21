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
数据资产和血缘分析工具
获取数据库表结构，生成数据资产目录和血缘分析。

直接使用 clickhouse-connect 通过 HTTPS(8123) 查询 system.tables / system.columns，
生成 schema / catalog / lineage 三份产物，无需额外的 MCP Server。

依赖: clickhouse-connect
"""

import os
import sys
import json
from datetime import datetime
from typing import Dict, List, Any

try:
    import clickhouse_connect  # noqa: F401
except ImportError:
    print("clickhouse-connect not installed. Please run: pip install clickhouse-connect")
    sys.exit(1)



def _create_client():
    """创建 ByteHouse 客户端。"""
    host = os.environ.get('BYTEHOUSE_HOST', '')
    if not host:
        raise ValueError("BYTEHOUSE_HOST is required")
    user = os.environ.get('BYTEHOUSE_USER', 'bytehouse')
    password = os.environ.get('BYTEHOUSE_PASSWORD', '')
    port = int(os.environ.get('BYTEHOUSE_PORT', '8123'))

    return clickhouse_connect.get_client(
        host=host,
        port=port,
        username=user,
        password=password,
        secure=True,
        verify=False,
    )


def _extract_engine(create_query: str) -> str:
    """从CREATE TABLE语句中提取引擎"""
    if "ENGINE = " in create_query:
        parts = create_query.split("ENGINE = ")
        if len(parts) > 1:
            engine_part = parts[1].split("\n")[0].split("(")[0].strip()
            return engine_part
    return "Unknown"


def _generate_tags(table: Dict[str, Any]) -> List[str]:
    """为表生成标签"""
    tags = []

    # 引擎标签
    engine = table.get("engine", "")
    if "Distributed" in engine:
        tags.append("分布式表")
    elif "MergeTree" in engine:
        tags.append("MergeTree系列")
    elif "Log" in engine:
        tags.append("日志引擎")

    # 表名模式标签
    name = table.get("name", "").lower()
    if any(kw in name for kw in ["log", "event", "trace"]):
        tags.append("日志/事件")
    if any(kw in name for kw in ["order", "trans", "pay"]):
        tags.append("交易/订单")
    if any(kw in name for kw in ["user", "customer", "account"]):
        tags.append("用户/客户")
    if any(kw in name for kw in ["product", "item", "goods"]):
        tags.append("商品/物料")
    if any(kw in name for kw in ["daily", "hourly", "monthly"]):
        tags.append("时序聚合")
    if any(kw in name for kw in ["dim", "dimension"]):
        tags.append("维度表")
    if any(kw in name for kw in ["fact"]):
        tags.append("事实表")

    # 列数标签
    col_count = len(table.get("columns", []))
    if col_count > 50:
        tags.append("宽表")
    elif col_count < 5:
        tags.append("窄表")

    return tags if tags else ["未分类"]


def _list_tables(client, database: str) -> List[Dict[str, Any]]:
    sql = (
        "SELECT name, engine, create_table_query, comment "
        "FROM system.tables "
        f"WHERE database = '{database}' "
        "AND name NOT LIKE '.inner%' AND name NOT LIKE '%_mv_%' "
        "ORDER BY name LIMIT 500"
    )
    rows = client.query(sql).result_rows
    tables: List[Dict[str, Any]] = []
    for name, engine, create_query, comment in rows:
        tables.append({
            "name": name,
            "engine": engine,
            "create_table_query": create_query,
            "comment": comment or "",
        })
    return tables


def _describe_table(client, database: str, table: str) -> List[Dict[str, Any]]:
    sql = (
        "SELECT name, type, comment "
        "FROM system.columns "
        f"WHERE database = '{database}' AND table = '{table}' "
        "ORDER BY position LIMIT 500"
    )
    rows = client.query(sql).result_rows
    return [
        {"name": name, "type": col_type, "comment": comment or ""}
        for name, col_type, comment in rows
    ]


def analyze_database(database: str) -> Dict[str, Any]:
    """
    分析数据库结构

    Args:
        database: 目标数据库名

    Returns:
        分析结果字典
    """
    print(f"📊 正在分析数据库: {database}")
    print("-" * 80)

    client = _create_client()
    try:
        print("✅ 连接成功！")

        # 1. 列出所有表
        print(f"\n1️⃣  列出所有表...")
        tables = _list_tables(client, database)
        print(f"   找到 {len(tables)} 张表")

        # 2. 解析表结构
        print(f"\n2️⃣  解析表结构...")
        schema = {
            "database": database,
            "analyzed_at": datetime.now().isoformat(),
            "tables": [],
        }

        for i, table in enumerate(tables, 1):
            table_name = table.get("name", "unknown")
            print(f"   [{i}/{len(tables)}] 处理表: {table_name}")

            table_info = {
                "name": table_name,
                "comment": table.get("comment", ""),
                "engine": _extract_engine(table.get("create_table_query", "")),
                "create_table_query": table.get("create_table_query", ""),
                "columns": [],
            }

            columns = _describe_table(client, database, table_name)
            for column in columns:
                table_info["columns"].append({
                    "name": column.get("name", ""),
                    "type": column.get("type", ""),
                    "comment": column.get("comment", ""),
                })

            schema["tables"].append(table_info)

        # 3. 生成数据资产目录
        print(f"\n3️⃣  生成数据资产目录...")
        catalog = {
            "database": database,
            "generated_at": datetime.now().isoformat(),
            "total_tables": len(schema["tables"]),
            "total_columns": sum(len(t["columns"]) for t in schema["tables"]),
            "engine_distribution": {},
            "tables_catalog": [],
        }

        # 统计引擎分布
        for table in schema["tables"]:
            engine = table["engine"]
            catalog["engine_distribution"][engine] = catalog["engine_distribution"].get(engine, 0) + 1

        # 生成表目录
        for table in schema["tables"]:
            table_entry = {
                "name": table["name"],
                "engine": table["engine"],
                "column_count": len(table["columns"]),
                "tags": _generate_tags(table),
                "columns": [
                    {"name": col["name"], "type": col["type"]}
                    for col in table["columns"][:10]
                ],
                "has_more_columns": len(table["columns"]) > 10,
            }
            catalog["tables_catalog"].append(table_entry)

        # 4. 生成血缘分析
        print(f"\n4️⃣  生成血缘分析...")
        lineage: Dict[str, Any] = {
            "database": database,
            "analyzed_at": datetime.now().isoformat(),
            "table_relationships": [],
            "column_similarities": [],
        }

        # 分析表关系（基于表名模式）
        tables_list = schema["tables"]
        table_map = {t["name"]: t for t in tables_list}

        for table in tables_list:
            table_name = table["name"]

            # 查找相关表（基于命名模式）
            related_tables: List[Dict[str, str]] = []

            # Distributed 表 -> Local 表
            if "Distributed" in table["engine"]:
                local_name = table_name.replace("_local", "")
                if local_name in table_map:
                    related_tables.append({
                        "name": local_name,
                        "relationship": "Distributed -> Local",
                    })

            # Local 表 -> Distributed 表
            local_pattern = f"{table_name}_local"
            if local_pattern in table_map:
                related_tables.append({
                    "name": local_pattern,
                    "relationship": "Local -> Distributed",
                })

            if related_tables:
                lineage["table_relationships"].append({
                    "table": table_name,
                    "related_tables": related_tables,
                })

        # 分析列相似性
        column_names: Dict[str, List[Dict[str, str]]] = {}
        for table in tables_list:
            for column in table["columns"]:
                col_name = column["name"]
                if col_name not in column_names:
                    column_names[col_name] = []
                column_names[col_name].append({
                    "table": table["name"],
                    "type": column["type"],
                })

        # 找出重复列名
        for col_name, occurrences in column_names.items():
            if len(occurrences) > 1:
                lineage["column_similarities"].append({
                    "column_name": col_name,
                    "occurrences": occurrences,
                })

        return {
            "schema": schema,
            "catalog": catalog,
            "lineage": lineage,
        }
    finally:
        try:
            client.close()
        except Exception:
            pass


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python data_asset_analyzer.py <database>")
        print("示例: python data_asset_analyzer.py test_db")
        sys.exit(1)

    database = sys.argv[1]

    print("=" * 80)
    print("ByteHouse 数据资产和血缘分析工具")
    print("=" * 80)
    print()
    print("⚠️  请确保已设置以下环境变量:")
    print("  - BYTEHOUSE_HOST")
    print("  - BYTEHOUSE_PORT")
    print("  - BYTEHOUSE_USER")
    print("  - BYTEHOUSE_PASSWORD")
    print()

    try:
        result = analyze_database(database)

        # 保存结果
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 保存 schema
        schema_file = os.path.join(output_dir, f"schema_{database}_{timestamp}.json")
        with open(schema_file, "w", encoding="utf-8") as f:
            json.dump(result["schema"], f, ensure_ascii=False, indent=2)

        # 保存 catalog
        catalog_file = os.path.join(output_dir, f"catalog_{database}_{timestamp}.json")
        with open(catalog_file, "w", encoding="utf-8") as f:
            json.dump(result["catalog"], f, ensure_ascii=False, indent=2)

        # 保存 lineage
        lineage_file = os.path.join(output_dir, f"lineage_{database}_{timestamp}.json")
        with open(lineage_file, "w", encoding="utf-8") as f:
            json.dump(result["lineage"], f, ensure_ascii=False, indent=2)

        # 打印摘要
        print("\n" + "=" * 80)
        print("📊 数据资产和血缘分析摘要")
        print("=" * 80)
        print(f"\n📁 数据库: {database}")
        print(f"📋 总表数: {result['catalog']['total_tables']}")
        print(f"📝 总列数: {result['catalog']['total_columns']}")

        print(f"\n🔧 引擎分布:")
        for engine, count in sorted(result['catalog']['engine_distribution'].items()):
            print(f"  - {engine}: {count} 张表")

        print(f"\n🔗 表关系: {len(result['lineage']['table_relationships'])} 组")
        print(f"📊 相似列: {len(result['lineage']['column_similarities'])} 组")

        print(f"\n🏷️  表标签示例:")
        for table_entry in result['catalog']['tables_catalog'][:5]:
            print(f"  - {table_entry['name']}: {', '.join(table_entry['tags'])}")

        print(f"\n📁 输出文件已保存到: {output_dir}")
        print(f"   - Schema: {os.path.basename(schema_file)}")
        print(f"   - 数据资产目录: {os.path.basename(catalog_file)}")
        print(f"   - 血缘分析: {os.path.basename(lineage_file)}")

        print("\n✅ 分析完成！")

    except Exception as e:
        print(f"\n❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
