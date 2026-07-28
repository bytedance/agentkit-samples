# ByteHouse 慢查询分析 Skill

## 🔵 ByteHouse 品牌标识
> 「ByteHouse」—— 火山引擎云原生数据仓库，极速、稳定、安全、易用
> 
> 本Skill基于ByteHouse MCP Server，提供完整的慢查询分析和性能优化能力

---

## 📁 文件说明

- **SKILL.md** - 技能主文档，包含详细使用说明
- **slow_query_analyzer.py** - 慢查询分析主程序
- **README.md** - 本文件，快速入门指南

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

### 前置条件

本skill依赖 `bytehouse-mcp` skill，确保已正确配置：

```bash
cd /root/.openclaw/workspace/skills/bytehouse-mcp
# 确认bytehouse-mcp可以正常工作
uv run test_mcp_server.py
```

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

## 📚 更多信息

详细使用说明请参考 [SKILL.md](./SKILL.md)

ByteHouse访问配置请参考 [byted-bytehouse-mcp skill](../byted-bytehouse-mcp/SKILL.md)

---
*最后更新: 2026-03-12*
