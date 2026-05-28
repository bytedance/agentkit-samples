---
name: byted-volcengine-vmp
description: 火山引擎托管 Prometheus (VMP) 查询技能，用于查询 VMP 工作区，以及查询 Prometheus 指标数据。
---

# 火山引擎托管 Prometheus (VMP) 管理 Skill

这个 Skill 用于查询和管理火山引擎的托管 Prometheus (VMP) 工作区，以及查询 Prometheus 指标数据。

## 何时使用此 Skill

当用户要求：

- 查询 VMP 工作区列表
- 查看工作区详细信息
- 查询 Prometheus 指标数据（PromQL 查询）
- 查询指标名称和标签

## 前置要求

需要安装火山引擎 Python SDK&#x20;

```bash
pip install --upgrade "volcengine-python-sdk>=5.0.21"
```

## 认证配置


推荐在 `~/.openclaw/workspace/.env` 中配置：

```env
VOLCENGINE_AK=your_access_key
VOLCENGINE_SK=your_secret_key
VOLCENGINE_REGION=cn-beijing
```

也可以通过环境变量设置：

```bash
export VOLCENGINE_AK=your_access_key
export VOLCENGINE_SK=your_secret_key
export VOLCENGINE_REGION=cn-beijing
```

认证读取优先级如下：

1. 进程环境变量
2. `--env-path` 指定的 `.env`
3. 默认 `.env`：`~/.openclaw/workspace/.env`

## 支持的主要功能

### 1. 工作区管理

- 查询工作区列表

### 2. Metrics 查询（新增）

- **即时查询** - 使用 PromQL 查询单个时间点的指标
- **范围查询** - 使用 PromQL 查询时间范围的指标
- **查询指标名称** - 查询工作区中的所有指标名称
- **查询指标标签** - 查询指定指标的所有标签

💡 **提示**: 常用的火山方舟 PromQL 告警查询可参考 `references/README.md` 文件，里面包含 15 个常用的监控告警查询语句！

## 使用示例

### 查询 VMP 工作区列表

```bash
python /root/.openclaw/workspace/skills/byted-volcengine-vmp/scripts/list_workspaces.py
```

### 即时查询 Metrics（PromQL）

```bash
# 查询当前时间的 CPU 使用率
python /root/.openclaw/workspace/skills/byted-volcengine-vmp/scripts/query_metrics.py \
  --workspace-id <workspace-id> \
  --query "sum(rate(container_cpu_usage_seconds_total[5m]))"
```

### 范围查询 Metrics（时间范围）

```bash
# 查询最近 1 小时的 CPU 使用率
python /root/.openclaw/workspace/skills/byted-volcengine-vmp/scripts/query_range_metrics.py \
  --workspace-id <workspace-id> \
  --query "sum(rate(container_cpu_usage_seconds_total[5m]))" \
  --start "2026-04-06T20:00:00+08:00" \
  --end "2026-04-06T21:00:00+08:00"
```

### 查询指标名称列表

```python
# 查询工作区中的所有指标名称
python /root/.openclaw/workspace/skills/byted-volcengine-vmp/scripts/get_metric_names.py \
  --workspace-id <workspace-id>

# 带匹配条件查询
python /root/.openclaw/workspace/skills/byted-volcengine-vmp/scripts/get_metric_names.py \
  --workspace-id <workspace-id> \
  --match '{job=~"kubelet"}'
```

### 查询指标标签列表

```python
# 查询指定指标的所有标签
python /root/.openclaw/workspace/skills/byted-volcengine-vmp/scripts/get_metric_labels.py \
  --workspace-id <workspace-id> \
  --metric-name up
```

## API 说明

### 工作区管理

#### ListWorkspaces

查询 VMP 工作区列表

**参数说明：**

- 无特殊参数

**返回：**
VMP 工作区列表

### Metrics 查询

#### QueryMetrics（即时查询）

执行 PromQL 即时查询

**参数说明：**

- `workspaceId`: 工作区 ID
- `query`: PromQL 查询语句
- `time`: 查询时间（可选，默认为当前时间）

**返回：**
PromQL 查询结果

#### QueryMetricsRange（范围查询）

执行 PromQL 范围查询

**参数说明：**

- `workspaceId`: 工作区 ID
- `query`: PromQL 查询语句
- `start`: 起始时间
- `end`: 结束时间
- `step`: 查询步长（可选，自动计算）

**返回：**
PromQL 范围查询结果

#### GetLabelValues

查询标签值

**参数说明：**

- `workspaceId`: 工作区 ID
- `label`: 标签名称（如 `__name__` 表示指标名称）
- `match`: 匹配条件（可选）

**返回：**
标签值列表

#### GetLabels

查询标签名称

**参数说明：**

- `workspaceId`: 工作区 ID
- `match`: 匹配条件（可选）

**返回：**
标签名称列表

## 常见 Region

默认地域：`cn-beijing`

| 地域        | Region ID        |
| --------- | ---------------- |
| 华北 2（北京）  | `cn-beijing`     |
| 华东 2（上海）  | `cn-shanghai`    |
| 华南 1（广州）  | `cn-guangzhou`   |
| 中国香港      | `cn-hongkong`    |
| 亚太东南（柔佛）  | `ap-southeast-1` |
| 亚太东南（雅加达） | `ap-southeast-3` |