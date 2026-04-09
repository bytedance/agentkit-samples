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
ByteHouse 负载分析工具
分析集群资源使用、查询负载、表负载等
"""

# /// script
# dependencies = [
#   "mcp>=1.0.0",
# ]
# ///

import asyncio
import os
import json
from datetime import datetime, timedelta
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
            'parts': 'system.cnch_parts_info'
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


async def run_load_analysis():
    """运行负载分析"""
    print("=" * 80)
    print("ByteHouse 负载分析工具")
    print("=" * 80)
    print()
    print("⚠️  请确保已设置以下环境变量:")
    print("  - BYTEHOUSE_HOST")
    print("  - BYTEHOUSE_PORT")
    print("  - BYTEHOUSE_USER")
    print("  - BYTEHOUSE_PASSWORD")
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
            
            # 分析结果
            analysis = {
                "analysis_time": datetime.now().isoformat(),
                "resource_usage": {},
                "query_load": {},
                "table_load": {},
                "bottleneck_analysis": [],
                "recommendations": []
            }
            
            # 1. 获取查询负载统计
            print("\n1️⃣  获取查询负载统计...")
            try:
                query_log_table = get_system_table_name('query_log')
                if not query_log_table:
                    print("   ℹ️  环境不支持查询日志表")
                    analysis["query_load"] = {
                        "time_range": "last_1_hour",
                        "stats": "Not supported in this environment"
                    }
                else:
                    sql = f"""
                        SELECT 
                            count(*) as query_count,
                            avg(query_duration_ms) as avg_duration_ms,
                            max(query_duration_ms) as max_duration_ms,
                            sum(read_rows) as total_read_rows,
                            sum(read_bytes) as total_read_bytes,
                            sum(written_rows) as total_written_rows,
                            sum(written_bytes) as total_written_bytes
                        FROM {query_log_table}
                        WHERE 
                            type = 'QueryFinish'
                            AND event_time > now() - interval 1 hour
                    """
                    result = await session.call_tool("run_select_query", {"query": sql})
                
                    query_load_data = []
                    for content in result.content:
                        if content.type == 'text':
                            query_load_data = content.text
                    
                    analysis["query_load"] = {
                        "time_range": "last_1_hour",
                        "stats": query_load_data
                    }
                    print("   ✅ 成功获取查询负载统计")
            except Exception as e:
                print(f"   ⚠️  获取查询负载统计失败: {e}")
            
            # 2. 获取表负载统计（基于parts表）
            print("\n2️⃣  获取表负载统计...")
            try:
                parts_table = get_system_table_name('parts')
                if not parts_table:
                    print("   ℹ️  环境不支持parts表")
                    analysis["table_load"] = {
                        "top_tables": "Not supported in this environment"
                    }
                else:
                    parts_columns = get_parts_table_columns()
                    sql = f"""
                        SELECT 
                            database,
                            table,
                            sum({parts_columns['rows']}) as total_rows,
                            sum({parts_columns['bytes']}) as total_bytes,
                            count(*) as part_count,
                            sum(if({parts_columns['active_condition']}, 1, 0)) as active_part_count
                        FROM {parts_table}
                        WHERE database != 'system'
                        GROUP BY database, table
                        ORDER BY total_bytes DESC
                        LIMIT 20
                    """
                    result = await session.call_tool("run_select_query", {"query": sql})
                
                    table_load_data = []
                    for content in result.content:
                        if content.type == 'text':
                            table_load_data = content.text
                    
                    analysis["table_load"] = {
                        "top_tables": table_load_data
                    }
                    print("   ✅ 成功获取表负载统计")
            except Exception as e:
                print(f"   ⚠️  获取表负载统计失败: {e}")
            
            # 3. 获取QPS趋势（按分钟）
            print("\n3️⃣  获取QPS趋势...")
            try:
                query_log_table = get_system_table_name('query_log')
                if not query_log_table:
                    print("   ℹ️  环境不支持查询日志表")
                    analysis["query_load"]["qps_trend"] = "Not supported in this environment"
                else:
                    sql = f"""
                        SELECT 
                            toStartOfMinute(event_time) as time_bucket,
                            count(*) as qps
                        FROM {query_log_table}
                        WHERE 
                            type = 'QueryFinish'
                            AND event_time > now() - interval 1 hour
                        GROUP BY time_bucket
                        ORDER BY time_bucket DESC
                        LIMIT 60
                    """
                    result = await session.call_tool("run_select_query", {"query": sql})
                
                    qps_trend_data = []
                    for content in result.content:
                        if content.type == 'text':
                            qps_trend_data = content.text
                    
                    analysis["query_load"]["qps_trend"] = qps_trend_data
                    print("   ✅ 成功获取QPS趋势")
            except Exception as e:
                print(f"   ⚠️  获取QPS趋势失败: {e}")
            
            # 4. 获取当前正在执行的查询
            print("\n4️⃣  获取当前正在执行的查询...")
            try:
                processes_table = get_system_table_name('processes')
                if processes_table:
                    # CE和CDW都使用system.processes表
                    sql = f"""
                        SELECT 
                            query_id,
                            query,
                            elapsed,
                            read_rows,
                            read_bytes
                        FROM {processes_table}
                        LIMIT 10
                    """
                    result = await session.call_tool("run_select_query", {"query": sql})
                    current_queries_data = []
                    for content in result.content:
                        if content.type == 'text':
                            current_queries_data = content.text
                    
                    analysis["query_load"]["current_queries"] = current_queries_data
                    print("   ✅ 成功获取当前查询")
                else:
                    print("   ℹ️  环境不支持获取当前查询")
                    analysis["query_load"]["current_queries"] = "Not supported in this environment"
            except Exception as e:
                print(f"   ⚠️  获取当前查询失败: {e}")
            
            # 5. 生成负载分析和建议
            print("\n5️⃣  生成负载分析和建议...")
            recommendations = []
            
            recommendations.append({
                "type": "monitoring",
                "priority": "high",
                "title": "持续监控查询负载",
                "description": "建议设置监控告警，关注QPS和查询延迟变化",
                "action": "配置Grafana或类似监控工具，实时监控查询性能"
            })
            
            recommendations.append({
                "type": "resource",
                "priority": "medium",
                "title": "资源扩容评估",
                "description": "根据表大小增长趋势，评估是否需要扩容存储",
                "action": "定期检查表大小增长率，规划容量"
            })
            
            recommendations.append({
                "type": "optimization",
                "priority": "medium",
                "title": "查询优化",
                "description": "分析Top N慢查询，进行针对性优化",
                "action": "使用慢查询分析工具，识别性能瓶颈"
            })
            
            recommendations.append({
                "type": "partition",
                "priority": "low",
                "title": "分区优化",
                "description": "检查表分区策略，考虑更细粒度的分区",
                "action": "评估分区键选择，优化查询性能"
            })
            
            analysis["recommendations"] = recommendations
            print(f"   ✅ 生成了 {len(recommendations)} 条建议")
            
            # 6. 瓶颈分析
            bottleneck_analysis = []
            
            bottleneck_analysis.append({
                "type": "query_pattern",
                "description": "检查是否有热点查询模式",
                "status": "needs_analysis"
            })
            
            bottleneck_analysis.append({
                "type": "table_size",
                "description": "监控大表增长趋势",
                "status": "needs_monitoring"
            })
            
            bottleneck_analysis.append({
                "type": "resource_usage",
                "description": "评估CPU、内存、磁盘使用情况",
                "status": "needs_monitoring"
            })
            
            analysis["bottleneck_analysis"] = bottleneck_analysis
            print(f"   ✅ 完成瓶颈分析")
            
            # 保存分析结果
            output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
            os.makedirs(output_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(output_dir, f"load_analysis_{timestamp}.json")
            
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(analysis, f, ensure_ascii=False, indent=2)
            
            # 打印分析摘要
            print("\n" + "=" * 80)
            print("📊 负载分析摘要")
            print("=" * 80)
            print(f"\n分析时间: {analysis['analysis_time']}")
            print(f"\n瓶颈分析: {len(analysis['bottleneck_analysis'])} 项")
            print(f"\n优化建议: {len(analysis['recommendations'])} 条")
            print(f"\n前3条建议:")
            for i, rec in enumerate(analysis['recommendations'][:3], 1):
                print(f"  {i}. [{rec['priority'].upper()}] {rec['title']}")
                print(f"     {rec['description']}")
            print(f"\n📁 分析报告已保存到: {output_file}")
            print("\n" + "=" * 80)


async def main():
    """主函数"""
    try:
        await run_load_analysis()
        print("\n✅ 负载分析完成！")
    except Exception as e:
        print(f"\n❌ 负载分析失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
