---
name: byted-bytehouse-mcp
description: 在本地拉起ByteHouse MCP Server并调用其tools的技能，用于连接ByteHouse数据库查询数据、使用MCP协议与ByteHouse交互、生成数据资产目录和血缘分析。当用户需要连接ByteHouse数据库查询数据、使用MCP协议与ByteHouse交互、生成数据资产目录和血缘分析时，使用此Skill。
version: 1.0.0
---

# ByteHouse MCP Server Skill

## 🔵 ByteHouse 品牌标识
> 「ByteHouse」—— 火山引擎云原生数据仓库，极速、稳定、安全、易用
> 
> 本Skill基于ByteHouse官方MCP Server，提供完整的ByteHouse数据访问能力

---

## 描述

在本地拉起ByteHouse MCP Server并调用其tools的技能。

**当以下情况时使用此 Skill**:
(1) 需要连接ByteHouse数据库查询数据
(2) 需要使用MCP协议与ByteHouse交互
(3) 用户提到"ByteHouse"、"MCP"、"查询数据库"、"看表"
(4) 需要生成数据资产目录和血缘分析

## 🎯 ByteHouse MCP Server Tools

| 序号 | Tool名称 | 功能描述 |
|------|----------|----------|
| 1 | **list_databases** | 列出所有数据库 |
| 2 | **list_tables** | 列出指定数据库中的所有表 |
| 3 | **run_select_query** | 运行SELECT查询 |
| 4 | **run_dml_ddl_query** | 运行DML/DDL查询 |
| 5 | **get_bytehouse_table_engine_doc** | 获取ByteHouse表引擎文档 |

## 📁 文件说明

- **SKILL.md** - 本文件，技能主文档
- **mcp_client.py** - MCP客户端模块，用于程序化调用MCP Server
- **test_mcp_server.py** - MCP Server测试脚本
- **example_mcp_usage.py** - MCP使用示例
- **query_top10_tables_mcp.py** - 使用MCP查询Top 10大表
- **test_list_tables.py** - 测试list_tables tool
- **data_asset_analyzer.py** - 数据资产和血缘分析工具（新增）
- **start_mcp_service.sh** - 启动常驻MCP Server服务
- **stop_mcp_service.sh** - 停止MCP Server服务
- **status_mcp_service.sh** - 查看MCP Server状态
- **restart_mcp_service.sh** - 重启MCP Server服务

## 配置说明
配置保存在 `~/.bytehouse_config.json` ，如果该文件存在且非空，则直接使用文件中的配置。如果不存在，则让用户提供ByteHouse连接信息（ 把这个文档也发给客户，文档里面介绍了如何获取主机地址和密码：https://www.volcengine.com/docs/6517/1121919?lang=zh ）。用户提供信息后，保存到json文件，避免重复向用户请求连接信息。当用户切换ByteHouse集群时，一并修改该文件。

```json
{
   "BYTEHOUSE_HOST": "<ByteHouse-host>",
   "BYTEHOUSE_PORT": "8123",
   "BYTEHOUSE_USER": "bytehouse",
   "BYTEHOUSE_PASSWORD": "<ByteHouse-password>",
   "BYTEHOUSE_SECURE": true,
   "BYTEHOUSE_VERIFY": true, 
   "BH_ARK_API_KEY": "<火山引擎方舟API密钥>",
   "BH_ARK_BASE_URL": "https://ark.cn-beijing.volces.com/api/v3",
   "BH_EMBEDDING_MODEL": "doubao-embedding-vision-251215"
}
```
其中BYTEHOUSE_HOST（主机地址）和BYTEHOUSE_PASSWORD（密码）**必须由**用户提供。BH_ARK_API_KEY为可选配置，仅在embedding时使用，用户初次使用时可忽略。其余配置固定。

## 前置条件

- Python 3.8+
- uv (已安装在 `/root/.local/bin/uv`)
- ByteHouse连接信息（需自行配置）

## 🚀 快速开始

### 方法1: 测试MCP Server（推荐先测试）

```bash
# 从配置文件读取配置，导出到环境变量
source scripts/export_config.sh
# 测试mcp server
uv run scripts/test_mcp_server.py
```

这会：
1. 自动安装ByteHouse MCP Server
2. 启动MCP Server
3. 列出所有可用的tools
4. 尝试调用第一个tool

### 方法2: 列出数据库中的表

```bash
cd /root/.openclaw/workspace/skills/bytehouse-mcp
# 先设置环境变量，然后运行
uv run test_list_tables.py
```

### 方法3: 使用MCP查询Top 10大表

```bash
cd /root/.openclaw/workspace/skills/bytehouse-mcp
# 先设置环境变量，然后运行
uv run query_top10_tables_mcp.py
```

### 方法4: 生成数据资产和血缘分析（新增）

```bash
cd /root/.openclaw/workspace/skills/bytehouse-mcp
# 先设置环境变量，然后运行
uv run data_asset_analyzer.py
```

这会：
1. 获取数据库的完整schema
2. 生成数据资产目录
3. 生成血缘分析报告
4. 保存JSON文件到 `output/` 目录

**输出内容包括：**
- 数据库schema（所有表和字段）
- 数据资产目录（表统计、标签、引擎分布）
- 血缘分析（表关系、列相似性）

### 方法5: 启动常驻MCP Server服务

```bash
cd /root/.openclaw/workspace/skills/bytehouse-mcp
# 先在脚本中配置环境变量，然后运行
./start_mcp_service.sh
```

这会：
1. 在后台启动MCP Server
2. 保存PID到 `mcp_server.pid`
3. 写入日志到 `logs/mcp_server_*.log`

### 方法6: 查看MCP Server状态

```bash
./status_mcp_service.sh
```

### 方法7: 停止MCP Server

```bash
./stop_mcp_service.sh
```

### 方法8: 重启MCP Server

```bash
./restart_mcp_service.sh
```

## 💻 数据资产和血缘分析（新增）

### 功能说明

`data_asset_analyzer.py` 提供以下功能：

1. **完整Schema获取**
   - 获取指定数据库的所有表
   - 获取每张表的所有字段
   - 提取表引擎、注释等元数据

2. **数据资产目录生成**
   - 表统计（总表数、总列数）
   - 引擎分布统计
   - 自动标签生成
   - 表资产详情

3. **血缘分析**
   - 表关系识别（Distributed → Local）
   - 列相似性分析
   - 关系可视化

### 使用示例

```python
#!/usr/bin/env python3
# /// script
# dependencies = [
#   "mcp>=1.0.0",
# ]
# ///

import asyncio
from data_asset_analyzer import DataAssetAnalyzer

async def main():
    analyzer = DataAssetAnalyzer()
    await analyzer.connect()
    
    # 分析数据库
    result = await analyzer.analyze_database("default")
    
    # result 包含:
    # - schema: 完整的数据库schema
    # - catalog: 数据资产目录
    # - lineage: 血缘分析
    # - files: 生成的文件路径

asyncio.run(main())
```

### 输出文件

分析完成后会在 `output/` 目录生成以下文件：

1. **schema_{database}_{timestamp}.json** - 完整的数据库schema
2. **catalog_{database}_{timestamp}.json** - 数据资产目录
3. **lineage_{database}_{timestamp}.json** - 血缘分析报告

## 💻 程序化使用MCP Client

### 使用mcp_client.py模块

```python
#!/usr/bin/env python3
# /// script
# dependencies = [
#   "mcp>=1.0.0",
# ]
# ///

import asyncio
from mcp_client import ByteHouseMCPClient

async def main():
    async with ByteHouseMCPClient() as client:
        await client.connect()
        
        # 1. 列出所有tools
        tools = await client.list_tools()
        print("可用的tools:", [t['name'] for t in tools])
        
        # 2. 调用tool
        # result = await client.call_tool("tool_name", {"param": "value"})
        # print(result)

asyncio.run(main())
```

### 直接使用MCP SDK

```python
#!/usr/bin/env python3
# /// script
# dependencies = [
#   "mcp>=1.0.0",
# ]
# ///

import asyncio
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    # 设置环境变量（请自行配置）
    env = os.environ.copy()
    env.update({
        'BYTEHOUSE_HOST': '<ByteHouse-host>',
        'BYTEHOUSE_PORT': '<ByteHouse-port>',
        'BYTEHOUSE_USER': '<ByteHouse-user>',
        'BYTEHOUSE_PASSWORD': '<ByteHouse-password>',
        'BYTEHOUSE_SECURE': 'true',
        'BYTEHOUSE_VERIFY': 'true',
    })
    
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
    
    # 启动MCP Server并连接
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # 列出tools
            result = await session.list_tools()
            print("Tools:", [t.name for t in result.tools])
            
            # 调用tool
            # call_result = await session.call_tool("tool_name", {"param": "value"})

asyncio.run(main())
```

## 🔧 服务管理

### 启动服务
```bash
# 先配置环境变量，然后运行
./start_mcp_service.sh
```

### 查看状态
```bash
./status_mcp_service.sh
```

### 查看日志
```bash
# 查看最新日志
tail -f logs/mcp_server_*.log

# 查看特定日志文件
tail -f logs/mcp_server_20260312_184500.log
```

### 停止服务
```bash
./stop_mcp_service.sh
```

### 重启服务
```bash
./restart_mcp_service.sh
```

## 💻 使用MCP Tools示例

### 示例1: 列出所有数据库

```python
import asyncio
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    # 设置环境变量（请自行配置）
    env = os.environ.copy()
    env.update({
        'BYTEHOUSE_HOST': '<ByteHouse-host>',
        'BYTEHOUSE_PORT': '<ByteHouse-port>',
        'BYTEHOUSE_USER': '<ByteHouse-user>',
        'BYTEHOUSE_PASSWORD': '<ByteHouse-password>',
        'BYTEHOUSE_SECURE': 'true',
        'BYTEHOUSE_VERIFY': 'true',
    })
    
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
            
            # 调用list_databases
            result = await session.call_tool("list_databases", {})
            for content in result.content:
                if content.type == 'text':
                    print(content.text)

asyncio.run(main())
```

### 示例2: 列出数据库中的表

```python
# 调用list_tables
result = await session.call_tool("list_tables", {"database": "default"})
```

### 示例3: 运行SELECT查询

```python
# 调用run_select_query
sql = "SELECT * FROM default.conversation_feedback LIMIT 10"
result = await session.call_tool("run_select_query", {"query": sql})
```

### 示例4: 查询Top 10大表

```python
# 查询Top 10大表
sql = """
    SELECT 
        database,
        table,
        sum(bytes) as total_bytes,
        sum(rows) as total_rows
    FROM system.parts 
    WHERE active = 1
    GROUP BY database, table
    ORDER BY total_bytes DESC
    LIMIT 10
"""
result = await session.call_tool("run_select_query", {"query": sql})
```

---
*最后更新: 2026-03-12*
