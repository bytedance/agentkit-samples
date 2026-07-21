#!/usr/bin/env python3
# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.

import os
import sys
import argparse

try:
    import clickhouse_connect
except ImportError:
    print("clickhouse-connect not installed. Please run: pip install clickhouse-connect")
    sys.exit(1)


def get_client(host, password):
    host = host or os.environ.get('BYTEHOUSE_HOST', '')
    password = password or os.environ.get('BYTEHOUSE_PASSWORD', '')

    if not host:
        raise ValueError("BYTEHOUSE_HOST is required")
    if not password:
        raise ValueError("BYTEHOUSE_USER and BYTEHOUSE_PASSWORD are required")

    user = os.environ.get('BYTEHOUSE_USER', 'bytehouse')
    port = int(os.environ.get('BYTEHOUSE_PORT', '8123'))
    secure = True


    return clickhouse_connect.get_client(
        host=host,
        port=port,
        username=user,
        password=password,
        secure=secure,
        verify=False,
    )

def main():
    parser = argparse.ArgumentParser(description="ByteHouse 数据质量检查工具")
    parser.add_argument("--database", "-d", help="数据库名", required=True)
    parser.add_argument("--table", "-t", help="表名", required=True)
    
    args = parser.parse_args()
    database = args.database
    table = args.table

    try:
        client = get_client(None, None)
    except Exception as e:
        print(f"连接 ByteHouse 失败: {e}")
        sys.exit(1)

    try:
        columns_query = f"""
        SELECT name, type, is_in_partition_key, is_in_sorting_key, is_in_primary_key
        FROM system.columns
        WHERE database = '{database}' AND table = '{table}'
        """
        cols = client.query(columns_query).result_rows

        if not cols:
            print(f"错误: 找不到表 {database}.{table} 或该表没有列。")
            sys.exit(1)

        partition_keys = []
        sorting_keys = []
        primary_keys = []
        col_types = {}

        for row in cols:
            name, ctype, is_part, is_sort, is_pk = row
            col_types[name] = ctype
            if is_part: partition_keys.append(name)
            if is_sort: sorting_keys.append(name)
            if is_pk: primary_keys.append(name)

        key_cols = list(set(partition_keys + sorting_keys + primary_keys))

        if not key_cols:
            print(f"表 {database}.{table} 没有设置分区键、排序键或主键。")
            sys.exit(0)

        total_rows_res = client.query(f"SELECT count(*) FROM {database}.{table}").result_rows
        total_rows = total_rows_res[0][0] if total_rows_res else 0

        print(f"=== 表 {database}.{table} 数据质量分析报告 ===")
        print(f"总行数: {total_rows}")
        print(f"分区键: {', '.join(partition_keys) if partition_keys else '无'}")
        print(f"排序键: {', '.join(sorting_keys) if sorting_keys else '无'}")
        print(f"主键: {', '.join(primary_keys) if primary_keys else '无'}")
        print("=" * 45)

        if total_rows == 0:
            print("表为空，跳过详细分析。")
            sys.exit(0)

        # 用于收集总结结论的数据
        has_nulls = False
        has_duplicates = False
        has_abnormal_distribution = False
        null_details = []
        dup_details = []
        abnormal_details = []

        print("\n1. 关键列空值、零值及分布情况分析:")
        print("-" * 45)

        for col in key_cols:
            ctype = col_types[col]
            
            # 空值检查
            if 'Nullable' in ctype:
                null_count = client.query(f"SELECT countIf(isNull({col})) FROM {database}.{table}").result_rows[0][0]
            else:
                null_count = 0
                
            if null_count > 0:
                has_nulls = True
                null_details.append(f"{col}({null_count}行)")
            
            # 零值/空字符串检查
            zero_count = 0
            if any(t in ctype for t in ['Int', 'Float', 'Decimal']):
                zero_count = client.query(f"SELECT countIf({col} = 0) FROM {database}.{table}").result_rows[0][0]
            elif 'String' in ctype:
                zero_count = client.query(f"SELECT countIf({col} = '') FROM {database}.{table}").result_rows[0][0]
                
            # 分布检查
            top_freq = client.query(f"SELECT {col}, count(*) as cnt FROM {database}.{table} GROUP BY {col} ORDER BY cnt DESC LIMIT 5").result_rows

            print(f"▶ 列 [{col}] (类型: {ctype}):")
            print(f"  - 空值 (Null) 数量: {null_count} (占比: {null_count/total_rows*100:.2f}%)")
            
            if any(t in ctype for t in ['Int', 'Float', 'Decimal']):
                print(f"  - 零值 (0) 数量: {zero_count} (占比: {zero_count/total_rows*100:.2f}%)")
            elif 'String' in ctype:
                print(f"  - 空字符串 ('') 数量: {zero_count} (占比: {zero_count/total_rows*100:.2f}%)")
                
            print(f"  - 数据分布 (Top 5):")
            for val, cnt in top_freq:
                print(f"    * {val}: {cnt} 行 (占比: {cnt/total_rows*100:.2f}%)")
                # 检查严重的数据倾斜 (占比 > 90% 且 总行数较大)
                if cnt / total_rows > 0.90 and total_rows > 100:
                    has_abnormal_distribution = True
                    abnormal_details.append(f"{col}(值 '{val}' 占比 {cnt/total_rows*100:.1f}%)")
            print()

        print("2. 键重复情况分析:")
        print("-" * 45)

        def check_dup(keys, key_name):
            if not keys:
                return 0, 0
            keys_str = ", ".join(keys)
            dup_query = f"""
            SELECT sum(cnt), count(*) FROM (
                SELECT {keys_str}, count(*) as cnt 
                FROM {database}.{table} 
                GROUP BY {keys_str} 
                HAVING cnt > 1
            )
            """
            dup_res = client.query(dup_query).result_rows[0]
            dup_rows = dup_res[0] if dup_res[0] is not None else 0
            dup_groups = dup_res[1] if dup_res[1] is not None else 0
            
            print(f"▶ {key_name} [{keys_str}] 重复情况:")
            print(f"  - 存在重复的唯一键组合数: {dup_groups}")
            print(f"  - 涉及的重复行数: {dup_rows} (占比: {dup_rows/total_rows*100:.2f}%)")
            print()
            
            return dup_rows, dup_groups

        pk_dup_rows, _ = check_dup(primary_keys, "主键")
        if pk_dup_rows > 0:
            has_duplicates = True
            dup_details.append(f"主键重复(涉及 {pk_dup_rows} 行)")
            
        check_dup(sorting_keys, "排序键")

        print("3. 总结性结论:")
        print("-" * 45)
        
        # 综合判定
        is_qualified = not (has_nulls or has_duplicates or has_abnormal_distribution)
        
        if is_qualified:
            print("▶ 结论: 【合格】")
            print("  - 表数据质量良好。")
            print("  - 未发现关键列(主键/排序键/分区键)存在空值。")
            print("  - 未发现主键存在重复记录。")
            print("  - 未发现关键列存在严重的数据分布倾斜。")
        else:
            print("▶ 结论: 【存在风险】")
            if has_nulls:
                print(f"  - [警告] 发现关键列存在空值: {', '.join(null_details)}，这可能会影响索引和查询性能。")
            if has_duplicates:
                print(f"  - [警告] 发现主键不唯一: {', '.join(dup_details)}，请确认是否符合业务预期（如ReplacingMergeTree去重前的状态）。")
            if has_abnormal_distribution:
                print(f"  - [提示] 发现关键列存在数据分布严重倾斜: {', '.join(abnormal_details)}，这可能导致计算和存储不均衡。")
        print("=" * 45)
        print()

    except Exception as e:
        print(f"执行分析时发生错误: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()