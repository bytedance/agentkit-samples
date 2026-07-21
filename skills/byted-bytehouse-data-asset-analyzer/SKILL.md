---
name: byted-bytehouse-data-asset-analyzer
description: ByteHouse 数据资产和血缘分析 Skill。直接通过 clickhouse-connect 查询 system.tables / system.columns，抓取指定数据库的表结构、字段、引擎等元数据，生成数据资产目录、自动打标签，并识别 Distributed/Local 之间的血缘关系与列相似性。当用户提到 "ByteHouse 数据资产"、"数据资产盘点"、"表结构分析"、"血缘分析"、"字段分析"、"表引擎分布"、"元数据目录" 等诉求时使用本 Skill。
version: 1.0.2
---

# ByteHouse 数据资产和血缘分析 Skill

## 描述

直接通过 `clickhouse-connect` 连接 ByteHouse（HTTPS 8123），查询 `system.tables` / `system.columns` 扫描目标数据库的所有表与字段，生成三份产物：

- **Schema 报告** — 数据库完整表结构（引擎、字段、DDL 原文等）。
- **数据资产目录** — 表总数、列总数、引擎分布、自动标签。
- **血缘分析报告** — Distributed ↔ Local 关系、跨表同名列的相似性。

**当以下情况时使用此 Skill：**

1. 需要获取 ByteHouse 数据库的表结构和字段信息。
2. 需要生成数据资产目录、盘点数据资产。
3. 需要分析表之间的血缘关系（例如 Distributed → Local）。
4. 用户提到 "数据资产"、"血缘分析"、"表结构"、"字段分析" 等关键词。

## 前置条件

- Python 3.8+
- `clickhouse-connect`（安装方式：`pip install clickhouse-connect`）
- `jq`（`export_config.sh` 依赖，解析 JSON 配置。安装方式：`brew install jq` 或 `sudo apt install jq`）
- 有效的 ByteHouse 连接信息（保存于 `~/.bytehouse_config.json`）

## 📁 文件说明

- **SKILL.md** — 本文件，技能主文档。
- **scripts/data_asset_analyzer.py** — 数据资产和血缘分析主程序。
- **scripts/export_config.sh** — 从 `~/.bytehouse_config.json` 加载配置到环境变量（依赖 `jq`）。

## 配置说明

配置保存在 `~/.bytehouse_config.json`。如果文件存在且非空，直接使用；若不存在，向用户索要连接信息（可以把 [ByteHouse 连接信息获取指引](https://www.volcengine.com/docs/6517/1121919?lang=zh) 发给用户），拿到后写入 JSON 文件，避免重复询问。

```json
{
  "BYTEHOUSE_HOST": "<ByteHouse-host>",
  "BYTEHOUSE_PORT": "8123",
  "BYTEHOUSE_USER": "bytehouse",
  "BYTEHOUSE_PASSWORD": "<ByteHouse-password>"
}
```

配置项说明：

| 配置项 | 是否必填 | 默认值 | 说明 |
|--------|----------|--------|------|
| `BYTEHOUSE_HOST` | 是 | — | ByteHouse 网关域名 |
| `BYTEHOUSE_PORT` | 否 | `8123` | HTTP(S) 端口 |
| `BYTEHOUSE_USER` | 否 | `bytehouse` | 用户名 |
| `BYTEHOUSE_PASSWORD` | 是 | — | 密码 / API Key |

加载配置：

```bash
source scripts/export_config.sh
```

## 🧭 智能体使用指引

1. **确认配置**：`source scripts/export_config.sh`，确认 `BYTEHOUSE_HOST` 等环境变量已就绪。
2. **确认要分析的数据库**：若用户未指定，主动询问（例如 `default`、`tpcds`）。
3. **执行分析**：`python3 scripts/data_asset_analyzer.py <database>`，脚本会通过 `clickhouse-connect` 查询 `system.tables` / `system.columns` 拉取元数据。
4. **展示结果**：根据 `scripts/output/` 目录里的 3 份 JSON 结果，给出总表数、总列数、引擎分布、Top 血缘关系等要点。
5. **禁止臆造**：所有资产/血缘信息一律来自脚本产物，不要凭上下文猜测。

## 🎯 功能特性

### 1. 完整 Schema 获取

- 获取指定数据库的所有表。
- 获取每张表的所有字段。
- 提取表引擎、注释等元数据。
- 保留 CREATE TABLE 语句原文。

### 2. 数据资产目录生成

- 表统计（总表数、总列数）。
- 引擎分布统计。
- 自动标签生成。
- 表资产详情（含前 10 个字段预览）。

### 3. 血缘分析

- 表关系识别（Distributed ↔ Local，基于命名模式）。
- 列相似性分析（同名列跨表出现）。

## 🚀 快速开始

```bash
# 1. 加载配置（复用 ~/.bytehouse_config.json）
source scripts/export_config.sh

# 2. 执行分析（指定库名）
python3 scripts/data_asset_analyzer.py default
python3 scripts/data_asset_analyzer.py tpcds
```

**分析内容包括：**

- 数据库完整 schema（所有表和字段）。
- 数据资产目录（表统计、引擎分布、自动标签）。
- 血缘分析（表关系、列相似性）。

**输出文件（保存在与脚本同级的 `scripts/output/` 目录）：**

1. `schema_{database}_{timestamp}.json` — 完整的数据库 schema。
2. `catalog_{database}_{timestamp}.json` — 数据资产目录。
3. `lineage_{database}_{timestamp}.json` — 血缘分析报告。

## 💻 程序化调用

`scripts/data_asset_analyzer.py` 暴露的是一个**同步函数** `analyze_database(database)`（**不是** async，也**不是**类）。它返回内存中的分析结果字典，**本身不落盘**；如需生成 JSON 文件，请直接运行脚本 `main()`（即命令行方式）。

要在其他 Python 代码里调用：

```python
import os
import sys

# 把 scripts/ 目录加入 sys.path，以便直接 import 模块
SKILL_SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "scripts",
)
sys.path.insert(0, SKILL_SCRIPTS_DIR)

from data_asset_analyzer import analyze_database

# 前提：已经通过 `source scripts/export_config.sh` 或手工 export 设置了
# BYTEHOUSE_HOST / BYTEHOUSE_PORT / BYTEHOUSE_USER / BYTEHOUSE_PASSWORD 等环境变量
result = analyze_database("default")
# result 是一个字典，包含:
# - schema:  完整的数据库 schema
# - catalog: 数据资产目录
# - lineage: 血缘分析
```

## 📊 输出文件说明

### 1. Schema 文件 (`schema_*.json`)

包含数据库完整结构：

```json
{
  "database": "default",
  "analyzed_at": "2026-03-12T19:50:00",
  "tables": [
    {
      "name": "conversation_feedback",
      "comment": "",
      "engine": "Distributed",
      "create_table_query": "CREATE TABLE ...",
      "columns": [
        {
          "name": "session_id",
          "type": "String",
          "comment": ""
        }
      ]
    }
  ]
}
```

### 2. 数据资产目录 (`catalog_*.json`)

包含数据资产统计信息（注意：统计字段与 `tables_catalog` 位于顶层，没有额外的 `summary` 嵌套）：

```json
{
  "database": "default",
  "generated_at": "2026-03-12T19:50:00",
  "total_tables": 8,
  "total_columns": 45,
  "engine_distribution": {
    "Distributed": 4,
    "MergeTree": 3,
    "Log": 1
  },
  "tables_catalog": [
    {
      "name": "conversation_feedback",
      "engine": "Distributed",
      "column_count": 10,
      "tags": ["分布式表", "用户/客户"],
      "columns": [
        {"name": "session_id", "type": "String"}
      ],
      "has_more_columns": false
    }
  ]
}
```

> `columns` 仅收录前 10 个字段用于预览，`has_more_columns` 标记是否还有更多字段。

### 3. 血缘分析 (`lineage_*.json`)

包含表关系和列相似性：

```json
{
  "database": "default",
  "analyzed_at": "2026-03-12T19:50:00",
  "table_relationships": [
    {
      "table": "conversation_feedback",
      "related_tables": [
        {
          "name": "conversation_feedback_local",
          "relationship": "Local -> Distributed"
        }
      ]
    }
  ],
  "column_similarities": [
    {
      "column_name": "session_id",
      "occurrences": [
        {"table": "conversation_feedback", "type": "String"},
        {"table": "conversation_feedback_local", "type": "String"}
      ]
    }
  ]
}
```

## 🏷️ 自动标签生成

分析器会根据**表引擎**、**表名关键词**、**列数**自动生成标签（引擎类标签三者互斥，命中其一即止；其余规则可叠加；若均未命中则标记为 `未分类`）：

| 标签 | 触发条件 |
|------|----------|
| `分布式表` | 引擎为 `Distributed` |
| `MergeTree系列` | 引擎包含 `MergeTree`（且非 Distributed） |
| `日志引擎` | 引擎包含 `Log`（且非上述两类） |
| `日志/事件` | 表名包含 `log` / `event` / `trace` |
| `交易/订单` | 表名包含 `order` / `trans` / `pay` |
| `用户/客户` | 表名包含 `user` / `customer` / `account` |
| `商品/物料` | 表名包含 `product` / `item` / `goods` |
| `时序聚合` | 表名包含 `daily` / `hourly` / `monthly` |
| `维度表` | 表名包含 `dim` / `dimension` |
| `事实表` | 表名包含 `fact` |
| `宽表` | 列数 > 50 |
| `窄表` | 列数 < 5 |
| `未分类` | 未命中以上任意规则 |

## 失败兜底建议

| 现象 | 处理方式 |
|------|----------|
| `clickhouse-connect not installed` | 安装依赖：`pip install clickhouse-connect`。 |
| `BYTEHOUSE_HOST is required` / 未设置 | 引导用户提供连接信息，写入 `~/.bytehouse_config.json` 后重新 `source scripts/export_config.sh`。 |
| 连接失败 / 证书报错 | 脚本固定使用 HTTPS 且跳过证书校验（`secure=True`、`verify=False`）；请确认 `BYTEHOUSE_HOST`/端口可从公网访问。 |
| 分析结果为空 | 让用户确认库名是否正确、账号是否有查询 `system` 表的权限。 |
