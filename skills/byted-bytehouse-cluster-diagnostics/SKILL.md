---
name: byted-bytehouse-cluster-diagnostics
description: ByteHouse 集群诊断，健康检查，慢查询分析和负载分析的工具
version: 1.0.3
---

# ByteHouse 诊断集群 Skill

## 🔵 ByteHouse 品牌标识
> 「ByteHouse」—— 火山引擎云原生数据仓库，极速、稳定、安全、易用
> 
> 本Skill基于ByteHouse MCP Server，提供完整的集群诊断和健康检查能力

---

## 描述

ByteHouse集群诊断，健康检查，慢查询分析和负载分析的工具。

**当以下情况时使用此 Skill**:
(1) 需要检查ByteHouse集群健康状态，诊断集群问题和异常
(2) 需要识别和分析慢查询，提供性能优化建议
(3) 需要分析负载情况，计算组资源使用情况
(4) 需要分析查询吞吐量，识别性能瓶颈
(5) 用户提到"集群诊断"、"健康检查"、"慢查询"、"查询优化"、"性能分析"、"负载分析"、"资源使用"、"吞吐量"等等

## 前置条件

- Python 3.8+
- uv (已安装在 `/root/.local/bin/uv`)

## 📁 文件说明

- **SKILL.md** - 本文件，技能主文档
- **scripts/diagnostics.py** - 诊断主程序
- **scripts/export_config.sh** - 配置导出环境变量脚本（从~/.bytehouse_config.json读取）

## 配置说明
配置保存在 `~/.bytehouse_config.json` ，如果该文件存在且非空，则直接使用文件中的配置。如果不存在，则让用户提供ByteHouse连接信息（ 把这个文档也发给客户，文档里面介绍了如何获取主机地址和密码：https://www.volcengine.com/docs/6517/1121919?lang=zh ）。用户提供信息后，保存到json文件，避免重复向用户请求连接信息。当用户切换ByteHouse集群时，一并修改该文件。

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

## 使用方法

⚠️ **严格限制：**
本 Skill **仅允许**通过执行 `scripts/diagnostics.py` 来发送诊断问题。**严禁**自行连接 ByteHouse 集群去发送 SQL 或执行任何查询。所有的分析和诊断动作必须委托给 `diagnostics.py` 脚本来完成。

```bash
# 导入配置
source scripts/export_config.sh

# 执行诊断
python3 scripts/diagnostics.py "你的诊断问题"
```

例如：
```bash
python3 scripts/diagnostics.py "检查一下计算组的负载情况"
```
