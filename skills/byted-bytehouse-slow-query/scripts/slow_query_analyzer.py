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
ByteHouse 慢查询分析工具
分析慢查询、查询性能、优化建议
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
            'query_log': 'bh_system.query_log'
        }
        return table_mapping.get(table_name, table_name)
    else:
        return f'system.{table_name}'


async def run_slow_query_analysis():
    """运行慢查询分析"""
    print("=" * 80)
    print("ByteHouse 慢查询分析工具")
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
            
            # 分析结果
            analysis = {
                "analysis_time": datetime.now().isoformat(),
                "slow_queries": [],
                "query_stats": {},
                "optimization_suggestions": []
            }
            
            # 1. 查询最近1小时的慢查询
            print("\n1️⃣  查询最近1小时的慢查询...")
            try:
                query_log_table = get_system_table_name('query_log')
                if not query_log_table:
                    print("   ℹ️  环境不支持查询日志表")
                    analysis["slow_queries"] = {
                        "count": "Not supported",
                        "top_20": "Not supported in this environment"
                    }
                else:
                    sql = f"""
                        SELECT 
                            query_id,
                            query,
                            query_duration_ms,
                            read_rows,
                            read_bytes,
                            result_rows,
                            result_bytes,
                            exception,
                            event_time
                        FROM {query_log_table}
                        WHERE 
                            type = 'QueryFinish'
                            AND event_time > now() - interval 1 hour
                            AND query_duration_ms > 1000
                        ORDER BY query_duration_ms DESC
                        LIMIT 20
                    """
                    result = await session.call_tool("run_select_query", {"query": sql})
                
                    slow_queries_data = []
                    for content in result.content:
                        if content.type == 'text':
                            slow_queries_data = content.text
                    
                    # 简单解析，实际项目中需要更完善的解析
                    analysis["slow_queries"] = {
                        "count": "parsed_from_result",
                        "top_20": slow_queries_data
                    }
                    print("   ✅ 成功获取慢查询数据")
            except Exception as e:
                print(f"   ⚠️  获取慢查询失败: {e}")
            
            # 2. 查询统计信息
            print("\n2️⃣  获取查询统计...")
            try:
                query_log_table = get_system_table_name('query_log')
                if not query_log_table:
                    print("   ℹ️  环境不支持查询日志表")
                    analysis["query_stats"] = {
                        "time_range": "last_1_hour",
                        "stats": "Not supported in this environment"
                    }
                else:
                    sql = f"""
                        SELECT 
                            count(*) as total_queries,
                            avg(query_duration_ms) as avg_duration_ms,
                            sum(if(query_duration_ms > 1000, 1, 0)) as slow_query_count,
                            sum(if(exception != '', 1, 0)) as error_query_count,
                            sum(read_rows) as total_read_rows,
                            sum(read_bytes) as total_read_bytes
                        FROM {query_log_table}
                        WHERE 
                            type = 'QueryFinish'
                            AND event_time > now() - interval 1 hour
                    """
                    result = await session.call_tool("run_select_query", {"query": sql})
                
                    query_stats_data = []
                    for content in result.content:
                        if content.type == 'text':
                            query_stats_data = content.text
                    
                    analysis["query_stats"] = {
                        "time_range": "last_1_hour",
                        "stats": query_stats_data
                    }
                    print("   ✅ 成功获取查询统计")
            except Exception as e:
                print(f"   ⚠️  获取查询统计失败: {e}")
            
            # 3. 查询类型分布
            print("\n3️⃣  获取查询类型分布...")
            try:
                query_log_table = get_system_table_name('query_log')
                if not query_log_table:
                    print("   ℹ️  环境不支持查询日志表")
                    analysis["query_type_distribution"] = "Not supported in this environment"
                else:
                    sql = f"""
                        SELECT 
                            substring(query, 1, 20) as query_prefix,
                            count(*) as query_count,
                            avg(query_duration_ms) as avg_duration_ms
                        FROM {query_log_table}
                        WHERE 
                            type = 'QueryFinish'
                            AND event_time > now() - interval 1 hour
                        GROUP BY query_prefix
                        ORDER BY query_count DESC
                        LIMIT 10
                    """
                    result = await session.call_tool("run_select_query", {"query": sql})
                
                    query_types_data = []
                    for content in result.content:
                        if content.type == 'text':
                            query_types_data = content.text
                    
                    analysis["query_type_distribution"] = query_types_data
                    print("   ✅ 成功获取查询类型分布")
            except Exception as e:
                print(f"   ⚠️  获取查询类型分布失败: {e}")
            
            # 4. 生成优化建议
            print("\n4️⃣  生成优化建议...")
            suggestions = []
            
            # 基于慢查询的建议
            suggestions.append({
                "type": "general",
                "priority": "medium",
                "title": "监控慢查询",
                "description": "建议持续关注慢查询趋势，设置合理的慢查询阈值",
                "action": "定期审查slow_query_log，识别性能问题"
            })
            
            suggestions.append({
                "type": "index",
                "priority": "high",
                "title": "索引优化",
                "description": "检查慢查询的WHERE条件，考虑添加适当的索引",
                "action": "使用EXPLAIN分析查询执行计划，识别全表扫描"
            })
            
            suggestions.append({
                "type": "configuration",
                "priority": "medium",
                "title": "配置调优",
                "description": "检查max_memory_usage、max_threads等配置参数",
                "action": "根据查询模式调整ClickHouse配置参数"
            })
            
            analysis["optimization_suggestions"] = suggestions
            print(f"   ✅ 生成了 {len(suggestions)} 条优化建议")
            
            # 保存分析结果
            output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
            os.makedirs(output_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(output_dir, f"slow_query_analysis_{timestamp}.json")
            
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(analysis, f, ensure_ascii=False, indent=2)
            
            # 打印分析摘要
            print("\n" + "=" * 80)
            print("📊 慢查询分析摘要")
            print("=" * 80)
            print(f"\n分析时间: {analysis['analysis_time']}")
            print(f"\n优化建议: {len(analysis['optimization_suggestions'])} 条")
            print(f"\n前3条建议:")
            for i, suggestion in enumerate(analysis['optimization_suggestions'][:3], 1):
                print(f"  {i}. [{suggestion['priority'].upper()}] {suggestion['title']}")
                print(f"     {suggestion['description']}")
            print(f"\n📁 分析报告已保存到: {output_file}")
            print("\n" + "=" * 80)


async def main():
    """主函数"""
    try:
        await run_slow_query_analysis()
        print("\n✅ 慢查询分析完成！")
    except Exception as e:
        print(f"\n❌ 慢查询分析失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
