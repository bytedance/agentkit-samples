---
name: byted-bytehouse-cluster-diagnostics
description: ByteHouse 集群诊断工具，用于健康检查、慢查询分析、负载分析、性能瓶颈诊断和吞吐量分析。当用户提到 "ByteHouse 集群诊断"、"健康检查"、"慢查询"、"查询优化"、"性能分析"、"负载分析"、"资源使用"、"吞吐量"、"计算组"、"CPU/内存告警" 等运维排障诉求时，使用本 Skill。
version: 1.0.4
---

# ByteHouse 诊断集群 Skill

## 🔵 ByteHouse 品牌标识
> 「ByteHouse」—— 火山引擎云原生数据仓库，极速、稳定、安全、易用
>
> 本 Skill 基于 ByteHouse Matrix Agent，提供完整的集群诊断和健康检查能力

---

## 描述

ByteHouse 集群诊断、健康检查、慢查询分析和负载分析的一站式工具。所有诊断能力都通过 `scripts/diagnostics.py` 转发到 ByteHouse Matrix Agent（一个由 ByteHouse 官方维护的诊断专用 Agent），Skill 本身不直接连接集群、不执行 SQL、不做本地分析。

**当以下情况时使用此 Skill：**

1. 需要检查 ByteHouse 集群健康状态，诊断集群问题与异常。
2. 需要识别、分析慢查询并给出性能优化建议。
3. 需要分析负载情况、计算组资源使用情况（CPU、内存、并发等）。
4. 需要分析查询吞吐量、识别性能瓶颈、定位热点。
5. 用户提到 "集群诊断"、"健康检查"、"慢查询"、"查询优化"、"性能分析"、"负载分析"、"资源使用"、"吞吐量" 等关键词。

## 前置条件

- Python 3.8+
- Python 依赖：`requests`（未安装时使用 `pip install requests` 或 `python3 -m pip install requests`）
- `jq`（`export_config.sh` 依赖，用于解析 JSON 配置。未安装时可使用 `brew install jq`、`sudo apt install jq` 或 `sudo yum install jq`）
- 有效的 ByteHouse 集群连接信息（保存于 `~/.bytehouse_config.json`）

## 📁 文件说明

- **SKILL.md** — 本文件，技能主文档。
- **scripts/diagnostics.py** — 诊断主程序，负责把用户的诊断问题转发到 ByteHouse Matrix Agent。
- **scripts/export_config.sh** — 从 `~/.bytehouse_config.json` 加载配置到环境变量（依赖 `jq`）。

## 🧭 智能体使用指引（重要）

Agent 在接手集群诊断类任务时，按以下流程调度本 Skill：

1. **确认配置就绪**：
   - 检查 `~/.bytehouse_config.json` 是否存在且包含 `BYTEHOUSE_HOST` 和 `BYTEHOUSE_PASSWORD`。
   - 如果不存在或字段缺失，主动向用户索要连接信息，并按下方 JSON 结构补齐后再执行。可以把 [ByteHouse 连接信息获取指引](https://www.volcengine.com/docs/6517/1121919?lang=zh) 发给用户。
   - 加载配置：`source scripts/export_config.sh`。
2. **精化诊断问题**：结合用户原始问题、告警内容、时间范围（例如 "最近 1 小时"、"过去 24 小时"），拼装一个自然语言诊断问题（中文即可）。参考 [常见诊断问题范例](#常见诊断问题范例)。
3. **执行诊断**：`python3 scripts/diagnostics.py "你的诊断问题"`，透传 Matrix Agent 的流式响应。
4. **失败兜底**：若诊断脚本返回连接错误、超时、401/403 等，参考 [失败兜底建议](#失败兜底建议) 处理，切勿绕过脚本自行连接集群或执行 SQL。
5. **禁止越权操作**：本 Skill **仅允许**通过 `scripts/diagnostics.py` 发送诊断问题，**严禁**自行连接 ByteHouse 集群执行 SQL 或做本地分析。所有分析、优化建议都必须来自 Matrix Agent 的返回结果。

## 配置说明

配置保存在 `~/.bytehouse_config.json`。如果该文件存在且非空，直接使用文件中的配置；如果不存在，则向用户索要连接信息（可以把这个文档发给用户以便查阅：https://www.volcengine.com/docs/6517/1121919?lang=zh）。拿到用户提供的信息后，写入 JSON 文件，避免重复询问。当用户切换 ByteHouse 集群时，一并更新该文件。

```json
{
   "BYTEHOUSE_HOST": "<ByteHouse-host>",
   "BYTEHOUSE_PASSWORD": "<ByteHouse-password>"
}
```

- `BYTEHOUSE_HOST`（主机地址）与 `BYTEHOUSE_PASSWORD`（密码）**必须由用户提供**。
- 密码只写入 `~/.bytehouse_config.json`，**不要**在会话、日志或额外的 shell 脚本中回显。
- 加载配置：
  ```bash
  source scripts/export_config.sh
  ```

## 使用方法

```bash
# 1. 加载配置
source scripts/export_config.sh

# 2. 执行诊断
python3 scripts/diagnostics.py "你的诊断问题"
```

### 常见诊断问题范例

以下是经过验证、易得到高质量输出的诊断问题模板。Agent 可以在此基础上根据用户诉求补充时间窗口、计算组名、库表名等参数：

- **健康检查**：`"请对集群做一次整体健康检查，重点检查节点存活、副本延迟、异常任务和错误日志"`
- **慢查询分析**：`"帮我识别过去 6 小时内 TOP 10 的慢查询，并给出优化建议"`
- **负载 & 资源**：`"分析各个计算组过去 24 小时的负载情况，包括 CPU、内存、并发、排队情况"`
- **吞吐量分析**：`"过去 1 小时集群 QPS、失败率、平均响应时间如何？有没有明显下滑或抖动"`
- **热点表分析**：`"看下 tpcds 库里过去 1 天最热的表和查询模式，有哪些可以优化的点"`
- **告警根因排查**：`"最近告警显示 warehouse_default CPU 持续超过 85%，帮我分析原因和缓解建议"`

### 高质量诊断问题的一些建议

- **明确时间窗口**：像 "最近 1 小时"、"过去 24 小时"、"今天 10:00-12:00" 都可以，越明确越好。
- **点名对象**：如果用户已经指定了库、表、计算组，务必带上。
- **只问一个问题**：一次诊断只聚焦一个主题，多个诉求拆成多次调用效果更好。
- **中文即可**：Matrix Agent 支持中文自然语言。
- **要求下一步动作**：可以加一句 "并给出优化建议 / 下一步排查方向"，让输出更贴合运维使用。

## 失败兜底建议

| 现象 | 处理方式 |
|------|----------|
| `BYTEHOUSE_HOST` 未设置 | 引导用户提供连接信息，写入 `~/.bytehouse_config.json` 后重新 `source scripts/export_config.sh`。 |
| 401 / 403 或 `Authorization` 相关错误 | 让用户确认 `BYTEHOUSE_PASSWORD` 是否与集群一致；密码变更后同步更新 JSON 文件。 |
| 连接超时 / 网络不通 | 让用户确认所在网络环境是否能访问 `BYTEHOUSE_HOST`（VPC、Endpoint 是否开放）。 |
| Matrix Agent 返回内容为空 / 太短 | 尝试补充时间窗口、点名对象后重新提问；或换一个更聚焦的问题重试。 |
| Python 报错 `ModuleNotFoundError: requests` | 提示用户执行 `pip install requests` 或 `python3 -m pip install --user requests`。 |
| `jq` 未安装 | 提示用户按前置条件安装 `jq`；作为临时兜底，可让用户手动 `export BYTEHOUSE_HOST=...`、`export BYTEHOUSE_PASSWORD=...`。 |

## 示例

```bash
# 加载配置
source scripts/export_config.sh

# 计算组负载诊断
python3 scripts/diagnostics.py "检查一下计算组的负载情况，重点看 CPU 和内存"

# 慢查询分析
python3 scripts/diagnostics.py "帮我识别过去 6 小时的 TOP 10 慢查询，并给出优化建议"

# 集群健康检查
python3 scripts/diagnostics.py "对集群做一次整体健康检查，找出潜在风险"
```
