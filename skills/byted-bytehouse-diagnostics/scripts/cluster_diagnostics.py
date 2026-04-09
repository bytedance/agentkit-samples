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
ByteHouse 集群诊断工具
检查集群健康状态、节点状态、副本同步等
"""

# /// script
# dependencies = [
#   "mcp>=1.0.0",
# ]
# ///

import asyncio
import os
import json
from datetime import datetime
from typing import Dict, List, Any
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def is_cdw_environment():
    """检测是否为CDW环境
    根据BYTEHOUSE_HOST判断：
    - CDW: tenant-xxxx-cn-shanghai-public.bytehouse.volces.com
    - CE: xxxx-public.bytehouse-ce.volces.com
    """
    host = os.environ.get('BYTEHOUSE_HOST', '')
    return '.bytehouse.volces.com' in host and '.bytehouse-ce.volces.com' not in host


def get_system_table_name(table_name):
    """根据环境返回正确的系统表名
    """
    if is_cdw_environment():
        table_mapping = {
            'query_log': 'bh_system.query_log',
            'processes': 'system.processes',
            'parts': 'system.cnch_parts_info',
            'replicas': None,  # CDW不需要
            'clusters': None,  # CDW不需要
            'mutations': 'system.mutations'  # CDW可能支持
        }
        return table_mapping.get(table_name, table_name)
    else:
        return f'system.{table_name}'


def get_parts_table_columns():
    """根据环境返回parts表的正确字段名
    """
    if is_cdw_environment():
        # CDW system.cnch_parts_info 表字段
        return {
            'rows': 'total_rows_count',
            'bytes': 'total_parts_size',
            'active': 'ready_state',
            'active_condition': "ready_state = 'Loaded'"
        }
    else:
        # CE system.parts 表字段
        return {
            'rows': 'rows',
            'bytes': 'bytes',
            'active': 'active',
            'active_condition': 'active'
        }


async def run_cluster_diagnostics():
    """运行集群诊断"""
    print("=" * 80)
    print("ByteHouse 集群诊断工具")
    print("=" * 80)
    print()
    print("⚠️  请确保已设置以下环境变量:")
    print("  - BYTEHOUSE_HOST")
    print("  - BYTEHOUSE_PORT")
    print("  - BYTEHOUSE_USER")
    print("  - BYTEHOUSE_PASSWORD")
    print()
    
    # 检测环境类型
    env_type = "CDW" if is_cdw_environment() else "CE"
    print(f"🔍 检测到环境类型: {env_type}")
    print()
    
    # 从环境变量获取配置
    env = os.environ.copy()
    
    # MCP Server参数
    server_params = StdioServerParameters(
        command='/root/.local/bin/uvx',
        args=[
            '--from',
            'git+https://github.com/volcengine/mcp-server@main#subdirectory=server/mcp_server_bytehouse',
            'mcp_bytehouse',
            '-t',
            'stdio'
        ],
        env=env
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("✅ 连接成功！")
            
            # 诊断结果
            diagnostics = {
                "diagnosis_time": datetime.now().isoformat(),
                "checks": [],
                "overall_status": "unknown",
                "recommendations": []
            }
            
            # 1. 测试连接 - list_databases
            print("\n1️⃣  检查集群连接...")
            try:
                result = await session.call_tool("list_databases", {})
                databases = []
                for content in result.content:
                    if content.type == 'text':
                        databases = [db.strip() for db in content.text.split('\n') if db.strip()]
                
                diagnostics["checks"].append({
                    "name": "cluster_connection",
                    "status": "pass",
                    "message": f"成功连接到ByteHouse，找到 {len(databases)} 个数据库",
                    "details": {"databases": databases}
                })
                print(f"   ✅ 通过 - 找到 {len(databases)} 个数据库")
            except Exception as e:
                diagnostics["checks"].append({
                    "name": "cluster_connection",
                    "status": "fail",
                    "message": f"连接失败: {str(e)}"
                })
                print(f"   ❌ 失败: {e}")
            
            # 2. 检查数据分区状态
            print("\n2️⃣  检查数据分区状态...")
            try:
                parts_table = get_system_table_name('parts')
                if not parts_table:
                    diagnostics["checks"].append({
                        "name": "parts_status",
                        "status": "info",
                        "message": "环境不支持parts表检查"
                    })
                    print("   ℹ️  信息: 环境不支持parts表检查")
                else:
                    parts_columns = get_parts_table_columns()
                    sql = f"""
                        SELECT 
                            database,
                            table,
                            count(*) as part_count,
                            sum({parts_columns['rows']}) as total_rows,
                            sum({parts_columns['bytes']}) as total_bytes,
                            sum(if({parts_columns['active_condition']}, 1, 0)) as active_parts
                        FROM {parts_table}
                        GROUP BY database, table
                        LIMIT 20
                    """
                    result = await session.call_tool("run_select_query", {"query": sql})
                    
                    part_info = []
                    for content in result.content:
                        if content.type == 'text':
                            part_info = content.text
                    
                    diagnostics["checks"].append({
                        "name": "parts_status",
                        "status": "pass",
                        "message": f"成功查询{parts_table}表",
                        "details": {"part_info": part_info}
                    })
                    print(f"   ✅ 通过 - {parts_table}表正常")
            except Exception as e:
                diagnostics["checks"].append({
                    "name": "parts_status",
                    "status": "warn",
                    "message": f"查询system.parts表失败: {str(e)}"
                })
                print(f"   ⚠️  警告: {e}")
            
            # 3. 检查system.mutations表
            print("\n3️⃣  检查Mutation状态...")
            try:
                sql = """
                    SELECT 
                        count(*) as pending_mutations,
                        sum(if(is_done=0, 1, 0)) as incomplete_mutations
                    FROM system.mutations
                """
                result = await session.call_tool("run_select_query", {"query": sql})
                
                mutation_info = []
                for content in result.content:
                    if content.type == 'text':
                        mutation_info = content.text
                
                diagnostics["checks"].append({
                    "name": "mutation_status",
                    "status": "pass",
                    "message": "成功查询system.mutations表",
                    "details": {"mutation_info": mutation_info}
                })
                print("   ✅ 通过 - system.mutations表正常")
            except Exception as e:
                diagnostics["checks"].append({
                    "name": "mutation_status",
                    "status": "warn",
                    "message": f"查询system.mutations表失败: {str(e)}"
                })
                print(f"   ⚠️  警告: {e}")
            
            # 4. 检查副本状态（仅CE环境）
            print("\n4️⃣  检查副本状态...")
            try:
                replicas_table = get_system_table_name('replicas')
                if is_cdw_environment() or not replicas_table:
                    # CDW是存算分离架构，不需要副本检查
                    diagnostics["checks"].append({
                        "name": "replica_status",
                        "status": "info",
                        "message": "CDW环境不需要副本状态检查（存算分离架构）"
                    })
                    print("   ℹ️  信息: CDW环境不需要副本状态检查")
                else:
                    sql = f"SELECT count(*) as replica_count FROM {replicas_table}"
                    result = await session.call_tool("run_select_query", {"query": sql})
                    
                    replica_info = []
                    for content in result.content:
                        if content.type == 'text':
                            replica_info = content.text
                    
                    diagnostics["checks"].append({
                        "name": "replica_status",
                        "status": "pass",
                        "message": f"成功查询{replicas_table}表",
                        "details": {"replica_info": replica_info}
                    })
                    print(f"   ✅ 通过 - {replicas_table}表正常")
            except Exception as e:
                diagnostics["checks"].append({
                    "name": "replica_status",
                    "status": "info",
                    "message": f"查询system.replicas表: {str(e)}"
                })
                print(f"   ℹ️  信息: {e}")
            
            # 5. 获取最近查询统计
            print("\n5️⃣  获取查询统计...")
            try:
                query_log_table = get_system_table_name('query_log')
                if not query_log_table:
                    diagnostics["checks"].append({
                        "name": "query_stats",
                        "status": "info",
                        "message": "环境不支持查询统计"
                    })
                    print("   ℹ️  信息: 环境不支持查询统计")
                else:
                    sql = f"""
                        SELECT 
                            count(*) as query_count,
                            sum(if(query_duration_ms > 1000, 1, 0)) as slow_query_count
                        FROM {query_log_table}
                        WHERE event_time > now() - interval 1 hour
                    """
                    result = await session.call_tool("run_select_query", {"query": sql})
                    
                    query_stats = []
                    for content in result.content:
                        if content.type == 'text':
                            query_stats = content.text
                    
                    diagnostics["checks"].append({
                        "name": "query_stats",
                        "status": "pass",
                        "message": "成功获取查询统计",
                        "details": {"query_stats": query_stats}
                    })
                    print("   ✅ 通过 - 查询统计正常")
            except Exception as e:
                diagnostics["checks"].append({
                    "name": "query_stats",
                    "status": "info",
                    "message": f"获取查询统计: {str(e)}"
                })
                print(f"   ℹ️  信息: {e}")
            
            # 计算整体状态
            pass_count = sum(1 for c in diagnostics["checks"] if c["status"] == "pass")
            warn_count = sum(1 for c in diagnostics["checks"] if c["status"] == "warn")
            fail_count = sum(1 for c in diagnostics["checks"] if c["status"] == "fail")
            
            if fail_count > 0:
                diagnostics["overall_status"] = "unhealthy"
            elif warn_count > 0:
                diagnostics["overall_status"] = "warning"
            else:
                diagnostics["overall_status"] = "healthy"
            
            # 生成建议
            if diagnostics["overall_status"] == "unhealthy":
                diagnostics["recommendations"].append("需要立即检查集群状态，解决失败的检查项")
            elif diagnostics["overall_status"] == "warning":
                diagnostics["recommendations"].append("关注警告项，建议进一步调查")
            else:
                diagnostics["recommendations"].append("集群状态健康，建议继续保持监控")
            
            # 保存诊断结果
            output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
            os.makedirs(output_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(output_dir, f"cluster_diagnostics_{timestamp}.json")
            
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(diagnostics, f, ensure_ascii=False, indent=2)
            
            # 打印诊断摘要
            print("\n" + "=" * 80)
            print("📊 诊断摘要")
            print("=" * 80)
            print(f"\n整体状态: {diagnostics['overall_status'].upper()}")
            print(f"\n检查结果:")
            print(f"  ✅ 通过: {pass_count}")
            print(f"  ⚠️  警告: {warn_count}")
            print(f"  ❌ 失败: {fail_count}")
            print(f"\n建议:")
            for rec in diagnostics["recommendations"]:
                print(f"  - {rec}")
            print(f"\n📁 诊断报告已保存到: {output_file}")
            print("\n" + "=" * 80)


async def main():
    """主函数"""
    try:
        await run_cluster_diagnostics()
        print("\n✅ 诊断完成！")
    except Exception as e:
        print(f"\n❌ 诊断失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
