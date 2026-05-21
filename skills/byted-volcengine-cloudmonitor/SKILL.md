---
name: byted-volcengine-cloudmonitor
description: 火山引擎云监控技能，用于查询云资源的监控时序数据。
---

# 火山引擎云监控 Skill

这个 Skill 用于查询火山引擎云监控的监控时序数据。

## 何时使用此 Skill

当用户要求：

- 通过云监控查询产品监控数据的时候

## 主要功能

### 1. 监控时序数据查询

- 完全控制所有参数
- 灵活的时间范围查询
- 支持多种监控指标
- 默认查询最近 5 分钟数据

### 2. 配置与调用方式

- 支持环境变量配置 `AK/SK`
- 支持 `.env` 文件配置
- 支持命令行直接使用
- 支持 Python 代码调用
- 支持 JSON 格式输出

## 处理逻辑

### 监控时序数据查询处理流程：

1. **根据客户提供的实例信息确定产品**
   - 识别产品类型（ECS、云服务器等）
2. **通过产品确定 namespace**
   - 自动映射到对应的产品命名空间
3. **通过监控指标确定 metric\_name/sub\_namespace**
   - 根据监控指标关键词自动确定
4. **结合 dimension 查询监控时序数据**
   - 如果没有指定时间范围，则按照默认**五分钟**查询

## 前置要求

需要安装火山引擎 Python SDK：

```bash
pip install --upgrade "volcengine-python-sdk>=5.0.21"
```

## 配置方式

需要配置火山引擎的 Access Key 和 Secret Key。推荐使用以下三种方式之一：

### 方式 1：环境变量

```bash
export VOLCENGINE_AK="your-ak"
export VOLCENGINE_SK="your-sk"
```

### 方式 2：`.env` 文件

在 `~/.openclaw/workspace/.env` 中配置：

```env
VOLCENGINE_AK=your-ak
VOLCENGINE_SK=your-sk
```

## 监控参数说明

### 监控时序数据查询核心参数

- **namespace**: 产品命名空间（如 VCM\_ECS）
- **metric\_name**: 监控指标名称（如 DiskUsageUtilization）
- **sub\_namespace**: 子命名空间（如 Instance）
- **dimension\_name**: 维度名称（如 ResourceID）
- **dimension\_value**: 维度值（如实例 ID）
- **start\_time**: 开始时间戳（可选，默认 5 分钟前）
- **end\_time**: 结束时间戳（可选，默认当前时间）
- **duration**: 查询时长（分钟，默认 5 分钟）

### 监控时序数据查询参数表

| 参数                  | 简写   | 说明          | 必填 | 默认值                        |
| ------------------- | ---- | ----------- | -- | -------------------------- |
| `--namespace`       | `-n` | 产品命名空间      | 是  | -                          |
| `--metric-name`     | `-m` | 监控指标名称      | 是  | -                          |
| `--sub-namespace`   | `-s` | 子命名空间       | 是  | -                          |
| `--dimension-name`  | `-d` | 维度名称        | 是  | -                          |
| `--dimension-value` | `-v` | 维度值         | 是  | -                          |
| `--start-time`      | -    | 开始时间戳       | 否  | `end_time - duration * 60` |
| `--end-time`        | -    | 结束时间戳       | 否  | 当前时间                       |
| `--duration`        | -    | 查询时长（分钟）    | 否  | `5`                        |
| `--ak`              | -    | Access Key  | 否  | 从配置读取                      |
| `--sk`              | -    | Secret Key  | 否  | 从配置读取                      |
| `--region`          | -    | 区域          | 否  | `cn-beijing`               |
| `--json`            | -    | 以 JSON 格式输出 | 否  | `False`                    |

### 时间参数说明

- 如果不指定 `--start-time` 和 `--end-time`，默认查询最近 **5 分钟**的数据。
- 可以使用 `--duration` 参数指定查询时长，单位为分钟。
- 时间戳格式为 Unix 时间戳，单位为秒。

## 如何获取监控参数

### 1. 获取产品命名空间（namespace）

可通过以下接口查询支持的监控产品：

```bash
curl 'https://cloudmonitor-api.console.volcengine.com/external/api/documents?Action=ListMetricProducts&Version=2018-01-01' \
  -H 'Content-Type: application/json' \
  --data-raw '{}'
```

### 2. 获取监控指标（metric\_name / sub\_namespace / dimension\_name）

在确定 `namespace` 后，可通过以下接口查询该产品的指标定义：

```bash
curl 'https://cloudmonitor-api.console.volcengine.com/external/api/documents?Action=ListMetricDocs&Version=2018-01-01' \
  -H 'Content-Type: application/json' \
  --data-raw '{"Namespace":"VCM_ECS"}'
```

## 参考资料

- 本地参考文档：`references/supported-cloud-products.md`
- 官方页面：`https://www.volcengine.com/docs/6408/1115078?lang=zh`
- 内容说明：收录云监控已接入的云产品列表、对应 `Namespace` 和监控数据保存时长，便于补充查询参数中的产品命名空间信息。

## 使用示例

### 高级模式

#### 指定时间范围查询

```bash
python get_metric_data.py \
  -n VCM_ECS \
  -m DiskUsageUtilization \
  -s Instance \
  -d ResourceID \
  -v i-yejc26eo744c5qwjqtgb \
  --start-time 1632903801 \
  --end-time 1632904801
```

#### 指定查询时长（分钟）

```bash
python get_metric_data.py \
  -n VCM_ECS \
  -m DiskUsageUtilization \
  -s Instance \
  -d ResourceID \
  -v i-yejc26eo744c5qwjqtgb \
  --duration 30
```

## API 说明

### GetMetricData

查询监控时序数据

**参数：**

- `end_time`: 结束时间戳（必填）
- `start_time`: 开始时间戳（必填）
- `namespace`: 产品命名空间（必填）
- `metric_name`: 监控指标名称（必填）
- `sub_namespace`: 子命名空间（必填）
- `instances`: 实例列表，包含维度信息（必填）

**返回：**
监控时序数据

## 常见问题

### Q: 如何获取当前时间戳？

A: 可以使用 Python 获取当前 Unix 时间戳：

```python
import time

current_timestamp = int(time.time())
print(current_timestamp)
```

### Q: 如何查询其他产品的监控数据？

A: 先调用 `ListMetricProducts` 获取所有产品，再调用 `ListMetricDocs` 获取指定产品的具体指标。

### Q: 时间戳格式是什么？

A: 使用 Unix 时间戳，单位为秒。例如 `1632903801` 表示一个秒级时间点。

### Q: 智能模式和高级模式有什么区别？

A:

- **智能模式**：只需提供产品、监控指标和实例 ID，脚本会自动推导其他参数。
- **高级模式**：需要显式提供 `namespace`、`metric_name`、`sub_namespace` 等参数，适合自动化或精确控制场景。