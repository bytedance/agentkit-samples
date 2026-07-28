# ByteHouse 负载分析 Skill

## 🔵 ByteHouse 品牌标识
> 「ByteHouse」—— 火山引擎云原生数据仓库，极速、稳定、安全、易用
> 
> 本Skill基于ByteHouse MCP Server，提供完整的集群负载分析和性能监控能力

---

## 📁 文件说明

- **SKILL.md** - 技能主文档，包含详细使用说明
- **load_analyzer.py** - 负载分析主程序
- **README.md** - 本文件，快速入门指南

## 🎯 功能特性

### 1. 资源使用分析
- CPU使用率监控
- 内存使用率分析
- 磁盘空间监控
- 网络流量统计

### 2. 查询负载分析
- QPS (每秒查询数) 统计
- 查询并发度分析
- 查询类型分布
- 高峰时段识别

### 3. 表负载分析
- 表访问热度排名
- 表读写比例分析
- 表大小增长趋势
- 分区负载分布

### 4. 性能瓶颈识别
- 资源瓶颈识别
- 查询队列分析
- 锁等待统计
- 优化建议生成

## 🚀 快速开始

### 前置条件

本skill依赖 `bytehouse-mcp` skill，确保已正确配置：

```bash
cd /root/.openclaw/workspace/skills/bytehouse-mcp
# 确认bytehouse-mcp可以正常工作
uv run test_mcp_server.py
```

### 方法1: 运行负载分析

```bash
cd /root/.openclaw/workspace/skills/bytehouse-load-analyzer

# 先设置环境变量（复用bytehouse-mcp的配置）
export BYTEHOUSE_HOST="<ByteHouse-host>"
export BYTEHOUSE_PORT="<ByteHouse-port>"
export BYTEHOUSE_USER="<ByteHouse-user>"
export BYTEHOUSE_PASSWORD="<ByteHouse-password>"
export BYTEHOUSE_SECURE="true"
export BYTEHOUSE_VERIFY="true"

# 运行负载分析
uv run load_analyzer.py
```

**分析内容包括：**
- 集群资源使用情况
- 查询负载统计
- 表访问热度
- 性能瓶颈识别
- 优化建议生成

**输出文件（保存在 `output/` 目录）：**
1. **`resource_usage_{timestamp}.json`** - 资源使用报告
2. **`query_load_{timestamp}.json`** - 查询负载报告
3. **`table_load_{timestamp}.json`** - 表负载报告
4. **`bottleneck_analysis_{timestamp}.json`** - 瓶颈分析报告

## 📚 更多信息

详细使用说明请参考 [SKILL.md](./SKILL.md)

ByteHouse访问配置请参考 [byted-bytehouse-mcp skill](../byted-bytehouse-mcp/SKILL.md)

---
*最后更新: 2026-03-12*
