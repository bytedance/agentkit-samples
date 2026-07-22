---
name: byted-volcengine-mongodb
description: 使用火山引擎 MongoDB Skill，帮助用户完成 MongoDB 相关的实例管理、备份恢复、参数等运维任务，可直接调用 uv run ./scripts/call_mongodb.py 脚本获取实时结果。当需要访问管理在火山引擎 MongoDB 实例详细信息时，此 Skill 可以提供方便的接口。
version: 1.0.0
metadata:
  display_name: 火山引擎云数据库 MongoDB 管理工具
  version: 1.0.0
  bins:
    - uv
  env:
    - VOLCENGINE_ACCESS_KEY
    - VOLCENGINE_SECRET_KEY
---

## Skill 概览

本 Skill 用于在对话中充当 **火山引擎 MongoDB 的智能运维代理**:

- **理解用户的自然语言需求**(中文或英文),识别是否与 MongoDB 相关;
- **直接调用内置脚本** `scripts/call_mongodb.py` 实时查询 MongoDB 并获取结果;
- 当获取到结果或用户粘贴错误信息时,**进一步解释、诊断并给出后续建议**。

**工作模式**:
- 使用 `scripts/call_mongodb.py` 脚本直接获取 MongoDB 的实时响应

**运行方式**:
脚本支持两种运行方式:
```bash
# 方式 1: 使用 uv (推荐，自动管理依赖)
uv run ./scripts/call_mongodb.py [action] [options]

# 方式 2: 使用 python (需要预先安装依赖)
python ./scripts/call_mongodb.py [action] [options]
```

## 标准使用流程

1. **确认任务类型与参数**
    - 判断用户意图:查询实例列表、查看实例详情、管理备份、查看参数配置等。
    - 收集必要参数(如未指定则使用默认值):
        - `--region`:地域 ID(默认 `cn-beijing`)
        - `--action`:操作类型(如 `list-instances`、`describe-instance`、`list-backups` 等)
        - `--instance-id`:实例 ID(部分操作必需)

2. **构造查询并调用脚本**
   - 示例（以下命令可使用 `uv run` 或 `python` 运行）:
     ```bash
     # 查询实例列表
     uv run ./scripts/call_mongodb.py list-instances

     # 查询指定实例详情
     uv run ./scripts/call_mongodb.py describe-instance --instance-id mongo-xxx

     # 查询实例备份
     uv run ./scripts/call_mongodb.py list-backups --instance-id mongo-xxx

     # 查询实例参数
     uv run ./scripts/call_mongodb.py list-parameters --instance-id mongo-xxx
     ```

3. **解析结果并后续处理**
    - 将 MongoDB 的响应用自然语言解释给用户;
    - 如返回包含敏感操作,评估风险并提醒:
        - 避免在生产环境直接执行高风险操作(如删除实例、重启等);
        - 建议在测试环境验证或做好备份。

## 工具脚本使用说明

### 支持的操作(Actions)

| 操作 | 说明 | 必需参数 |
|------|------|----------|
| `list-instances` | 查询 MongoDB 实例列表 | 无 |
| `describe-instance` | 查询指定实例详情 | `--instance-id` |
| `list-backups` | 查询实例备份 | `--instance-id` |
| `list-parameters` | 查询实例参数配置 | `--instance-id` |

### 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `action` | 操作类型(必需) | - |
| `--region` / `-r` | 火山引擎地域 ID | `cn-beijing` |
| `--instance-id` / `-i` | 实例 ID | 无 |
| `--page-number` | 分页页码 | `1` |
| `--page-size` | 每页记录数 | `10` |
| `--output` / `-o` | 输出格式(json/table) | `json` |

### 输出格式

脚本会将查询信息输出到 `stderr`,将结果输出到 `stdout`,便于分离日志和结果:

```
[操作] list-instances
[地域] cn-beijing
============================================================
[查询结果]
<实际结果内容>
```

## 使用示例

### 实例查询

#### 查看所有实例

```bash
uv run ./scripts/call_mongodb.py list-instances
```

**输出示例：**
```json
{
  "db_instances": [
    {
      "instance_id": "mongo-replica-e40665523086",
      "instance_name": "副本集只读控制面",
      "instance_status": "Running",
      "instance_type": "ReplicaSet",
      "db_engine_version_str": "MongoDB 4.0",
      "charge_type": "PostPaid",
      "create_time": "2026-07-22T06:37:45Z",
      "zone_id": "cn-beijing-d,cn-beijing-a,cn-beijing-c"
    }
  ],
  "total": 34
}
```

#### 查看指定实例详情

```bash
uv run ./scripts/call_mongodb.py describe-instance \
  --instance-id mongo-xxx
```

**输出示例：**
```json
{
  "db_instance": {
    "instance_id": "mongo-replica-e40665523086",
    "instance_name": "副本集只读控制面",
    "instance_status": "Running",
    "instance_type": "ReplicaSet",
    "db_engine_version_str": "MongoDB 4.0",
    "nodes": [
      {
        "node_id": "mongo-replica-e40665523086-0",
        "node_role": "Primary",
        "node_spec": "mongo.2c4g",
        "node_status": "Running"
      }
    ]
  }
}
```

### 运维管理

#### 查看实例备份列表

```bash
uv run ./scripts/call_mongodb.py list-backups \
  --instance-id mongo-xxx
```

**输出示例：**
```json
{
  "backups": [
    {
      "backup_id": "875c42ec8d574e95a885c301b0c5e593",
      "backup_file_name": "full-1784702562511139825",
      "backup_status": "Success",
      "backup_type": "Physical",
      "backup_start_time": "2026-07-22T06:42:30Z",
      "backup_file_size": 200644645
    }
  ],
  "total": 1
}
```

#### 查看实例参数配置

```bash
uv run ./scripts/call_mongodb.py list-parameters \
  --instance-id mongo-xxx
```

**输出示例：**
```json
{
  "db_engine": "MongoDB",
  "db_engine_version": "MongoDB_4_0",
  "instance_id": "mongo-replica-e40665523086",
  "instance_parameters": [
    {
      "parameter_names": "connPoolMaxConnsPerHost",
      "parameter_value": "600",
      "parameter_default_value": "600",
      "parameter_type": "Integer",
      "force_restart": true,
      "parameter_description": "设置当前实例或节点的全局连接池最大容量"
    }
  ]
}
```

## 环境变量配置

1. 获取火山引擎访问凭证：参考 [用户指南](https://www.volcengine.com/docs/6291/65568?lang=zh) 获取 AK/SK

2. 配置以下环境变量:

```bash
export VOLCENGINE_ACCESS_KEY="your-access-key"
export VOLCENGINE_SECRET_KEY="your-secret-key"
export VOLCENGINE_REGION="cn-beijing"  # 可选，默认 cn-beijing
```