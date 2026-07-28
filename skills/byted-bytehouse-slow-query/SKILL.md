---
name: byted-bytehouse-slow-query
description: ByteHouse慢查询分析和性能优化工具，用于识别和分析慢查询、查询性能优化建议、查看查询执行计划、分析查询历史趋势。当用户需要识别和分析ByteHouse数据库中的慢查询、查询性能优化建议、查看查询执行计划、分析查询历史趋势时，使用此Skill。
---

# ByteHouse 慢查询分析 Skill

## 🔵 ByteHouse 品牌标识
> 「ByteHouse」—— 火山引擎云原生数据仓库，极速、稳定、安全、易用
> 
> 本Skill基于ByteHouse MCP Server，提供完整的慢查询分析和性能优化能力

---

## 描述

ByteHouse慢查询分析和性能优化工具。

**当以下情况时使用此 Skill**:
(1) 需要识别和分析慢查询
(2) 需要查询性能优化建议
(3) 需要查看查询执行计划
(4) 需要分析查询历史趋势
(5) 用户提到"慢查询"、"查询优化"、"性能分析"、"执行计划"

## 前置条件

- Python 3.8+
- uv (已安装在 `/root/.local/bin/uv`)
- **ByteHouse MCP Server Skill** - 本skill依赖 `bytehouse-mcp` skill提供的ByteHouse访问能力

## 依赖关系

本skill依赖 `bytehouse-mcp` skill，使用其提供的MCP Server访问ByteHouse。

确保 `bytehouse-mcp` skill已正确配置并可以正常使用。

## 📁 文件说明

- **SKILL.md** - 本文件，技能主文档
- **slow_query_analyzer.py** - 慢查询分析主程序
- **README.md** - 快速入门指南

## 配置信息

### ByteHouse连接配置

本skill复用 `bytehouse-mcp` skill的配置。请确保已在 `bytehouse-mcp` skill中配置好：

```bash
export BYTEHOUSE_HOST="<ByteHouse-host>"
export BYTEHOUSE_PORT="<ByteHouse-port>"
export BYTEHOUSE_USER="<ByteHouse-user>"
export BYTEHOUSE_PASSWORD="<ByteHouse-password>"
export BYTEHOUSE_SECURE="true"
export BYTEHOUSE_VERIFY="true"
```

## 🎯 功能特性

### 1. 慢查询识别
- 从query_log表获取慢查询
- 按执行时间排序
- 识别Top N慢查询
- 分析慢查询模式

### 2. 查询性能分析
- 查询执行时间分布
- 查询类型统计
- 查询频率分析
- 性能趋势分析

### 3. 执行计划分析
- 获取查询执行计划
- 分析执行计划节点
- 识别性能瓶颈
- 提供优化建议

### 4. 优化建议生成
- 索引优化建议
- 查询重写建议
- 表引擎建议
- 配置参数调优

## 🚀 快速开始

### 方法1: 运行慢查询分析

```bash
cd /root/.openclaw/workspace/skills/bytehouse-slow-query

# 先设置环境变量（复用bytehouse-mcp的配置）
export BYTEHOUSE_HOST="<ByteHouse-host>"
export BYTEHOUSE_PORT="<ByteHouse-port>"
export BYTEHOUSE_USER="<ByteHouse-user>"
export BYTEHOUSE_PASSWORD="<ByteHouse-password>"
export BYTEHOUSE_SECURE="true"
export BYTEHOUSE_VERIFY="true"

# 运行慢查询分析
uv run slow_query_analyzer.py
```

**分析内容包括：**
- Top 20慢查询
- 查询性能统计
- 执行时间分布
- 优化建议生成

**输出文件（保存在 `output/` 目录）：**
1. **`slow_queries_{timestamp}.json`** - 慢查询列表
2. **`query_stats_{timestamp}.json`** - 查询统计报告
3. **`optimization_suggestions_{timestamp}.json`** - 优化建议

## 💻 慢查询分析维度

### 时间维度分析
- **按小时**: 每小时慢查询数量
- **按天**: 每天慢查询趋势
- **按周**: 每周慢查询模式
- **按月**: 每月慢查询统计

### 查询类型分析
- **SELECT查询**: 查询语句分析
- **INSERT查询**: 写入性能分析
- **UPDATE查询**: 更新性能分析
- **DELETE查询**: 删除性能分析
- **DDL查询**: 建表/改表性能分析

### 性能指标
- **平均执行时间**: 所有查询平均耗时
- **P50执行时间**: 中位数执行时间
- **P95执行时间**: 95分位执行时间
- **P99执行时间**: 99分位执行时间
- **最大执行时间**: 最慢查询耗时

---

## 📊 慢查询报告示例

### 慢查询列表
```json
{
  "analysis_time": "2026-03-12T21:00:00",
  "total_queries": 10000,
  "slow_queries": 150,
  "top_slow_queries": [
    {
      "query_id": "query-12345",
      "query_text": "SELECT * FROM large_table WHERE ...",
      "duration_ms": 15000,
      "start_time": "2026-03-12T20:55:00",
      "read_rows": 1000000,
      "read_bytes": 104857600
    }
  ]
}
```

---

## 📚 更多信息

详细使用说明请参考 [byted-bytehouse-mcp skill](../byted-bytehouse-mcp/SKILL.md)

---
*最后更新: 2026-03-12*
