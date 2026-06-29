---
name: byted-bytehouse-data-quality-inspector
description: ByteHouse 数据质量检查工具。当用户提供集群连接信息、数据库名和表名，需要检查排序键、主键和分区键所使用的列的空值、零值情况，是否存在异常分布，以及排序键、主键的重复情况时，使用此技能。
version: 1.0.0
---

# ByteHouse 数据质量检查工具

## 描述

本 Skill 用于对 ByteHouse 表的数据质量进行快速分析和检查。

**当以下情况时使用此 Skill**:
(1) 用户需要检查 ByteHouse 中某个表的数据质量
(2) 用户需要分析表的排序键、主键或分区键的空值、零值情况
(3) 用户想了解键列的数据分布情况
(4) 用户需要检查排序键和主键是否存在重复记录

## 前置条件

- Python 3.8+
- `clickhouse-connect` 库

## 📁 文件说明

- **SKILL.md** - 本文件，技能主文档
- **scripts/inspector.py** - 数据质量检查主程序
- **export_config.sh** - 配置导出环境变量脚本（从~/.bytehouse_config.json读取）

## 配置说明
配置保存在 `~/.bytehouse_config.json` ，如果该文件存在且非空，则直接使用文件中的配置。如果不存在，则让用户提供ByteHouse连接信息（ 把这个文档也发给用户，文档里面介绍了如何获取主机地址和密码：https://www.volcengine.com/docs/6517/1121919?lang=zh ）。用户提供信息后，保存到json文件，避免重复向用户请求连接信息。当用户切换ByteHouse集群时，一并修改该文件。

```json
{
   "BYTEHOUSE_HOST": "<ByteHouse-host>",
   "BYTEHOUSE_PASSWORD": "<ByteHouse-password>"
}
```
BYTEHOUSE_HOST（主机地址）和BYTEHOUSE_PASSWORD（密码）**必须由**用户提供

执行 `scripts/export_config.sh` 把配置信息导入环境变量中
```bash
source scripts/export_config.sh
```

## 🎯 功能特性

1. **自动识别键列**
   - 自动查询 `system.columns` 获取表的分区键、排序键和主键。

2. **空值与零值检查**
   - 统计上述键列的 Null 值数量和占比。
   - 针对数值类型统计 0 值的数量和占比；针对字符串类型统计空字符串的数量和占比。

3. **异常分布分析**
   - 统计上述键列中出现频率最高的 Top 5 值及占比。

4. **重复情况检查**
   - 分别针对主键组合、排序键组合，统计存在重复的唯一键组数以及涉及的总行数。

## 🚀 快速开始

```bash
source scripts/export_config.sh
python3 scripts/inspector.py --database <库名> --table <表名>
```

示例输出摘要:
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

- 对于超大表，统计去重和聚合可能会消耗一定的集群资源，请确保在合理的时间和资源范围内执行。
- 此工具只能检测出存在的重复或空值，但不能自动修复数据。
