---
name: byted-bytehouse-data-quality-inspector
description: ByteHouse 数据质量检查工具。当用户提供集群连接信息、数据库名和表名，需要检查排序键、主键和分区键所使用的列的空值、零值情况，是否存在异常分布，以及排序键、主键的重复情况时，使用此技能。适用于 "数据质量检查"、"排序键 / 主键 / 分区键分析"、"空值分析"、"零值分析"、"重复键检查"、"Top 分布" 等诉求。
version: 1.0.1
---

# ByteHouse 数据质量检查工具

## 描述

本 Skill 用于对 ByteHouse 表的关键键列（分区键、排序键、主键）进行快速数据质量分析，识别空值、零值、异常分布以及重复键等常见质量问题。

**当以下情况时使用此 Skill：**

1. 用户需要检查 ByteHouse 中某个表的数据质量。
2. 用户需要分析表的排序键、主键或分区键的空值、零值情况。
3. 用户想了解键列的数据分布情况（Top N 值及占比）。
4. 用户需要检查排序键 / 主键组合是否存在重复记录。
5. 用户提到 "数据质量"、"空值检查"、"零值检查"、"主键重复"、"排序键重复"、"分区键异常" 等关键词。

## 前置条件

- Python 3.8+
- `clickhouse-connect` 库（未安装时执行 `pip install clickhouse-connect`）
- `jq`（`export_config.sh` 依赖，用于解析 JSON 配置。安装方式：`brew install jq` 或 `sudo apt install jq`）
- 有效的 ByteHouse 连接信息（保存于 `~/.bytehouse_config.json`）

## 📁 文件说明

- **SKILL.md** — 本文件，技能主文档。
- **scripts/inspector.py** — 数据质量检查主程序。
- **scripts/export_config.sh** — 从 `~/.bytehouse_config.json` 加载配置到环境变量（依赖 `jq`）。

## 配置说明

配置保存在 `~/.bytehouse_config.json`。如果该文件存在且非空，直接使用文件中的配置；如果不存在，则向用户索要 ByteHouse 连接信息（可以把 [ByteHouse 连接信息获取指引](https://www.volcengine.com/docs/6517/1121919?lang=zh) 一并发给用户），拿到后写入 JSON 文件，避免重复询问。当用户切换 ByteHouse 集群时，一并更新该文件。

```json
{
   "BYTEHOUSE_HOST": "<ByteHouse-host>",
   "BYTEHOUSE_PASSWORD": "<ByteHouse-password>"
}
```

- `BYTEHOUSE_HOST`（主机地址）与 `BYTEHOUSE_PASSWORD`（密码）**必须由用户提供**。

加载配置：

```bash
source scripts/export_config.sh
```

## 🧭 智能体使用指引

1. **确认配置**：`source scripts/export_config.sh`，确保 `BYTEHOUSE_HOST` 与 `BYTEHOUSE_PASSWORD` 已就绪。
2. **确认目标表**：向用户确认要检查的库名（`--database`）和表名（`--table`）。多张表可以循环调用脚本。
3. **执行检查**：`python3 scripts/inspector.py --database <库名> --table <表名>`。
4. **解读结果**：脚本会分别输出「空值/零值/分布」和「主键/排序键重复情况」两大部分。若用户没有明确关注点，重点关注空值占比 > 1%、零值占比 > 5%、Top1 占比 > 20%、重复键行数占比 > 0.5% 等异常。
5. **禁止越权操作**：本 Skill 只做**只读**的统计查询，**不要**触发 DELETE / OPTIMIZE / DROP 等 DML/DDL 操作。修复数据应由用户在评估后单独操作。

## 🎯 功能特性

1. **自动识别键列**
   - 从 `system.columns` 自动获取表的分区键、排序键和主键列。

2. **空值与零值检查**
   - 统计键列的 Null 值数量和占比。
   - 数值类型统计 0 值数量和占比；字符串类型统计空字符串数量和占比。

3. **异常分布分析**
   - 统计键列出现频率最高的 Top 5 值及占比。

4. **重复情况检查**
   - 分别针对主键组合、排序键组合，统计存在重复的唯一键组数以及涉及的总行数。

## 🚀 快速开始

```bash
# 加载配置
source scripts/export_config.sh

# 检查单张表
python3 scripts/inspector.py --database default --table my_table
```

## 💡 常用姿势

- **批量检查多张表**：

  ```bash
  for tbl in orders order_items users; do
    python3 scripts/inspector.py --database default --table "$tbl"
  done
  ```

- **和资产分析结合**：先用 `byted-bytehouse-data-asset-analyzer` 输出的目录挑出重点表，再逐表跑本 Skill。

## 示例输出摘要

```text
=== 表 default.my_table 数据质量分析报告 ===
总行数: 1000000
分区键: date
排序键: user_id, event_time
主键: user_id
=============================================

1. 关键列空值、零值及分布情况分析:
---------------------------------------------
▶ 列 [user_id] (类型: String):
  - 空值 (Null) 数量: 0 (占比: 0.00%)
  - 空字符串 ('') 数量: 15 (占比: 0.00%)
  - 数据分布 (Top 5):
    * user_123: 500 行 (占比: 0.05%)
    ...

2. 键重复情况分析:
---------------------------------------------
▶ 主键 [user_id] 重复情况:
  - 存在重复的唯一键组合数: 850
  - 涉及的重复行数: 15000 (占比: 1.50%)
```

## 注意事项

- 对超大表运行统计聚合会占用一定的集群资源，请在业务低峰或独立计算组上执行。
- 本工具只**检测**质量问题，不做任何自动修复动作。
- 若目标表数据量特别大且用户可以接受抽样，可以先与用户确认后再让脚本增加 `SAMPLE` / `LIMIT`（当前脚本默认为全表统计）。

## 失败兜底建议

| 现象 | 处理方式 |
|------|----------|
| `BYTEHOUSE_HOST` 未设置 | 引导用户提供连接信息，写入 `~/.bytehouse_config.json` 后 `source scripts/export_config.sh`。 |
| `clickhouse-connect not installed` | `pip install clickhouse-connect` 或 `python3 -m pip install --user clickhouse-connect`。 |
| `找不到表 xxx` | 让用户确认库名、表名，或先用 `byted-bytehouse-ai-query` 的 `list_tables.py` 列表核对。 |
| 检查耗时过长 / 触发资源告警 | 建议在独立计算组或非业务高峰执行，必要时先只对疑似有问题的关键列做检查。 |
