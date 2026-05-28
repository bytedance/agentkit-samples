---
name: byted-bytehouse-data-asset-analyzer
description: 基于ByteHouse MCP Server，生成数据资产目录和血缘分析的技能，用于获取数据库表结构、生成数据资产目录、分析表之间的血缘关系。当用户需要获取ByteHouse数据库的表结构、生成数据资产目录、分析表之间的血缘关系时，使用此Skill。
version: 1.0.0
---

# ByteHouse 数据资产和血缘分析 Skill

## 描述

本Skill基于ByteHouse MCP Server，生成数据资产目录和血缘分析的技能。

**当以下情况时使用此 Skill**:
(1) 需要获取数据库表结构和字段信息
(2) 需要生成数据资产目录
(3) 需要分析表之间的血缘关系
(4) 用户提到"数据资产"、"血缘分析"、"表结构"、"字段分析"

## 前置条件

- Python 3.8+
- uv (已安装在 `/root/.local/bin/uv`)
- **ByteHouse MCP Server Skill** - 本skill依赖 `bytehouse-mcp` skill提供的ByteHouse访问能力

## 依赖关系

本skill依赖 `bytehouse-mcp` skill，使用其提供的MCP Server访问ByteHouse。

确保 `bytehouse-mcp` skill已正确配置并可以正常使用。

## 📁 文件说明

- **SKILL.md** - 本文件，技能主文档
- **data_asset_analyzer.py** - 数据资产和血缘分析主程序
- **README.md** - 快速入门指南

## 配置信息

### ByteHouse连接配置

本skill复用 `bytehouse-mcp` skill的配置。请确保已在 `bytehouse-mcp` skill中配置好

## 🎯 功能特性

### 1. 完整Schema获取
- 获取指定数据库的所有表
- 获取每张表的所有字段
- 提取表引擎、注释等元数据
- 解析CREATE TABLE语句

### 2. 数据资产目录生成
- 表统计（总表数、总列数）
- 引擎分布统计
- 自动标签生成
- 表资产详情

### 3. 血缘分析
- 表关系识别（Distributed → Local）
- 列相似性分析
- 关系可视化

## 🚀 快速开始

### 方法1: 运行数据资产和血缘分析

```bash
# 先设置环境变量（复用bytehouse-mcp的配置）
source scripts/export_config.sh
# 运行分析工具
uv run scripts/data_asset_analyzer.py
```

**分析内容包括：**
- 数据库完整schema（所有表和字段）
- 数据资产目录（表统计、引擎分布、自动标签）
- 血缘分析（表关系、列相似性）

**输出文件（保存在 `output/` 目录）：**
1. **`schema_{database}_{timestamp}.json`** - 完整的数据库schema
2. **`catalog_{database}_{timestamp}.json`** - 数据资产目录
3. **`lineage_{database}_{timestamp}.json`** - 血缘分析报告

## 💻 程序化使用

### 使用分析器模块

```python
#!/usr/bin/env python3
# /// script
# dependencies = [
#   "mcp>=1.0.0",
# ]
# ///

import asyncio
import sys
import os

# 添加bytehouse-mcp skill的路径
BYTEHOUSE_MCP_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "bytehouse-mcp"
)
sys.path.insert(0, BYTEHOUSE_MCP_PATH)

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

## 📊 输出文件说明

### 1. Schema文件 (`schema_*.json`)

包含数据库的完整结构：

```json
{
  "database": "default",
  "analyzed_at": "2026-03-12T19:50:00",
  "tables": [
    {
      "name": "conversation_feedback",
      "comment": "",
      "engine": "Distributed",
      "columns": [
        {
          "name": "session_id",
          "type": "String",
          "comment": ""
        }
      ],
      "create_table_query": "CREATE TABLE ..."
    }
  ]
}
```

### 2. 数据资产目录 (`catalog_*.json`)

包含数据资产的统计信息：

```json
{
  "database": "default",
  "generated_at": "2026-03-12T19:50:00",
  "summary": {
    "total_tables": 8,
    "total_columns": 45,
    "engines": {
      "Distributed": 4,
      "HaMergeTree": 3,
      "MergeTree": 1
    }
  },
  "tables": [
    {
      "name": "conversation_feedback",
      "comment": "",
      "engine": "Distributed",
      "column_count": 10,
      "columns": [...],
      "tags": ["distributed", "user-feedback"]
    }
  ]
}
```

### 3. 血缘分析 (`lineage_*.json`)

包含表关系和列相似性：

```json
{
  "database": "default",
  "generated_at": "2026-03-12T19:50:00",
  "table_relationships": [
    {
      "source_table": "conversation_feedback",
      "relationships": [
        {
          "type": "distributed_to_local",
          "target_table": "conversation_feedback_local",
          "description": "Distributed表指向Local表"
        }
      ]
    }
  ],
  "column_similarities": [
    {
      "column_name": "session_id",
      "column_type": "String",
      "found_in_tables": [
        "conversation_feedback",
        "conversation_feedback_local"
      ]
    }
  ]
}
```

## 🏷️ 自动标签生成

分析器会根据表名和引擎自动生成标签：

| 标签 | 说明 |
|------|------|
| `merge-tree` | 使用MergeTree引擎 |
| `distributed` | 使用Distributed引擎 |
| `high-availability` | 使用HaMergeTree或HaUniqueMergeTree |
| `log-table` | 表名包含"log" |
| `user-feedback` | 表名包含"feedback" |
| `local-table` | 表名以"_local"结尾 |
| `test-table` | 表名包含"test" |

## 📚 更多信息

详细使用说明请参考 [bytehouse-mcp skill](../bytehouse-mcp/SKILL.md)

---
*最后更新: 2026-03-12*
