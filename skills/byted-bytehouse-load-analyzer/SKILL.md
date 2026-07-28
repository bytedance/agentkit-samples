---
name: byted-bytehouse-load-analyzer
description: ByteHouse集群负载分析和性能监控工具，用于分析集群负载情况、监控资源使用情况、分析查询吞吐量、识别性能瓶颈。当用户需要分析ByteHouse集群负载情况、监控资源使用情况、分析查询吞吐量、识别性能瓶颈时，使用此Skill。
---

# ByteHouse 负载分析 Skill

## 🔵 ByteHouse 品牌标识
> 「ByteHouse」—— 火山引擎云原生数据仓库，极速、稳定、安全、易用
> 
> 本Skill基于ByteHouse MCP Server，提供完整的集群负载分析和性能监控能力

---

## 描述

ByteHouse集群负载分析和性能监控工具。

**当以下情况时使用此 Skill**:
(1) 需要分析集群负载情况
(2) 需要监控资源使用情况
(3) 需要分析查询吞吐量
(4) 需要识别性能瓶颈
(5) 用户提到"负载分析"、"性能监控"、"资源使用"、"吞吐量"

## 前置条件

- Python 3.8+
- uv (已安装在 `/root/.local/bin/uv`)
- **ByteHouse MCP Server Skill** - 本skill依赖 `bytehouse-mcp` skill提供的ByteHouse访问能力

## 依赖关系

本skill依赖 `bytehouse-mcp` skill，使用其提供的MCP Server访问ByteHouse。

确保 `bytehouse-mcp` skill已正确配置并可以正常使用。

## 📁 文件说明

- **SKILL.md** - 本文件，技能主文档
- **load_analyzer.py** - 负载分析主程序
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

## 💻 负载分析维度

### 资源维度
- **CPU**: 使用率、等待时间、上下文切换
- **内存**: 使用量、缓存、Swap使用
- **磁盘**: 使用率、IOPS、吞吐量
- **网络**: 入流量、出流量、连接数

### 时间维度
- **实时**: 当前负载情况
- **最近1小时**: 1小时内趋势
- **最近24小时**: 24小时内趋势
- **最近7天**: 7天内趋势
- **历史对比**: 同比环比分析

### 表维度
- **访问热度**: 查询次数排名
- **读写比例**: 读写操作比例
- **大小增长**: 表大小变化趋势
- **分区分布**: 分区数据分布

---

## 📊 负载报告示例

### 资源使用报告
```json
{
  "analysis_time": "2026-03-12T21:00:00",
  "cluster_name": "bh_log_boe",
  "resources": {
    "cpu": {
      "usage_percent": 65.5,
      "wait_time_ms": 15,
      "context_switches": 10000
    },
    "memory": {
      "used_gb": 128.5,
      "total_gb": 256.0,
      "usage_percent": 50.2
    },
    "disk": {
      "used_gb": 5120.0,
      "total_gb": 10240.0,
      "usage_percent": 50.0,
      "iops_read": 5000,
      "iops_write": 3000
    }
  }
}
```

### 查询负载报告
```json
{
  "analysis_time": "2026-03-12T21:00:00",
  "query_load": {
    "qps": 500,
    "concurrent_queries": 50,
    "query_types": {
      "SELECT": 70,
      "INSERT": 20,
      "UPDATE": 5,
      "DELETE": 3,
      "DDL": 2
    },
    "peak_hours": [
      "10:00-11:00",
      "14:00-15:00",
      "20:00-21:00"
    ]
  }
}
```

---

## 📚 更多信息

详细使用说明请参考 [byted-bytehouse-mcp skill](../byted-bytehouse-mcp/SKILL.md)

---
*最后更新: 2026-03-12*
