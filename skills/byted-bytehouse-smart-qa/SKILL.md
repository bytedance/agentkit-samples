---
name: byted-bytehouse-smart-qa
description: ByteHouse 智能问答技能
version: 1.0.0
---

# ByteHouse 智能问答 Skill

## 🔵 ByteHouse 品牌标识
> 「ByteHouse」—— 火山引擎云原生数据仓库，极速、稳定、安全、易用
> 
> 本Skill提供官网知识问答的能力

---

## 描述

ByteHouse官网知识问答技能

**当以下情况时使用此 Skill**:
用户询问ByteHouse产品功能，用户指南等相关问题，包括
(1) 计费相关问题
(2) AI相关问题
(3) 导入导出相关问题
(4) 租户管理相关问题
(5) 权限相关问题
(6) 其他相关问题，如审计日志、数据备份、生态工具等

## 前置条件

- Python 3.8+
- uv (已安装在 `/root/.local/bin/uv`)

## 📁 文件说明

- **SKILL.md** - 本文件，技能主文档
- **scripts/run.py** - 问答主程序
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
本 Skill **仅允许**通过执行 `scripts/run.py` 来发送问题。**严禁**自行连接 ByteHouse 集群去发送 SQL 或执行任何查询。所有问题必须委托给 `run.py` 脚本来完成。

```bash
# 导入配置
source scripts/export_config.sh

# 执行问答
python3 scripts/run.py "你的问题"
```

例如：
```bash
python3 scripts/run.py "ByteHouse是怎么计费的"
```
