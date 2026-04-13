---
name: byted-sqlserver-instance-management
description: 使用火山引擎 RDS SQL Server，当用户需要执行 RDS SQL Server 相关的实例管理、数据库操作、账号管理和运维任务时使用该skills，可直接调用 uv run ./scripts/call_rds_mssql.py 脚本获取实时结果。
version: 1.0.0
---

## Skill 概览

本 Skill 用于在对话中充当 **火山引擎 RDS SQL Server 的智能运维代理**:

- **理解用户的自然语言需求**(中文或英文),识别是否与 RDS SQL Server 相关;
- **直接调用内置脚本** `scripts/call_rds_mssql.py` 实时查询 RDS SQL Server 并获取结果;
- 当获取到结果或用户粘贴错误信息时,**进一步解释、诊断并给出后续建议**。

**工作模式**:
- 使用 `scripts/call_rds_mssql.py` 脚本直接获取 RDS SQL Server 的实时响应

**运行方式**:
脚本支持两种运行方式:
```bash
# 方式 1: 使用 uv (推荐，自动管理依赖)
uv run ./scripts/call_rds_mssql.py [action] [options]

# 方式 2: 使用 python (需要预先安装依赖)
python ./scripts/call_rds_mssql.py [action] [options]
```

## 标准使用流程

1. **确认任务类型与参数**
    - 判断用户意图: 查询实例列表、查看实例详情、查询账号列表、查询参数配置、查询 VPC、查询子网等。
    - 收集必要参数(如未指定则使用默认值):
        - `--region`: 地域 ID(默认 `cn-beijing`)
        - `action`: 操作类型(如 `list-instances`、`describe-instance`、`describe-db-accounts` 等)
        - `--instance-id`: 实例 ID(部分操作必需)
        - `--vpc-id`: VPC ID(部分操作必需)

2. **构造查询并调用脚本**
   - 示例（以下命令可使用 `uv run` 或 `python` 运行）:
     ```bash
     # 查询实例列表
     uv run ./scripts/call_rds_mssql.py list-instances 
     # 或
     python ./scripts/call_rds_mssql.py list-instances

     # 查询指定实例详情
     uv run ./scripts/call_rds_mssql.py describe-instance --instance-id mssql-xxx
     # 或
     python ./scripts/call_rds_mssql.py describe-instance --instance-id mssql-xxx

     # 查询实例的账号列表
     uv run ./scripts/call_rds_mssql.py describe-db-accounts --instance-id mssql-xxx
     # 或
     python ./scripts/call_rds_mssql.py describe-db-accounts --instance-id mssql-xxx

     # 查询实例参数
     uv run ./scripts/call_rds_mssql.py list-parameters --instance-id mssql-xxx
     # 或
     python ./scripts/call_rds_mssql.py list-parameters --instance-id mssql-xxx

     # 查询 VPC 列表
     uv run ./scripts/call_rds_mssql.py list-vpcs
     # 或
     python ./scripts/call_rds_mssql.py list-vpcs

     # 查询子网列表
     uv run ./scripts/call_rds_mssql.py list-subnets --vpc-id vpc-xxx --zone-id cn-beijing-a
     # 或
     python ./scripts/call_rds_mssql.py list-subnets --vpc-id vpc-xxx --zone-id cn-beijing-a

     ```

3. **解析结果并后续处理**
    - 将 RDS SQL Server 的响应用自然语言解释给用户;
    - 如返回包含敏感操作,评估风险并提醒:
        - 避免在生产环境直接执行高风险操作(如删除实例、删除数据库等);
        - 建议在测试环境验证或做好备份。

## 工具脚本使用说明

### 支持的接口(Actions)

| 操作 | 说明 | 必需参数 |
|------|------|----------|
| `list-instances` | 查询 RDS SQL Server 实例列表 | 无 |
| `describe-instance` | 查询指定实例详情 | `--instance-id` |
| `describe-db-accounts` | 查询实例的账号列表 | `--instance-id` |
| `list-parameters` | 查询实例的参数配置 | `--instance-id` |
| `list-vpcs` | 查询 VPC 列表 | 无 |
| `list-subnets` | 查询子网列表 | `--vpc-id` |

### 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `action` | 操作类型(必需) | - |
| `--region` / `-r` | 火山引擎地域 ID | `cn-beijing` |
| `--endpoint` | API 端点（可选） | - |
| `--page-number` | 分页页码（部分接口支持） | `1` |
| `--page-size` | 每页记录数（部分接口支持） | `10` |
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

## 常见使用场景

### 1. 查看所有实例
```bash
uv run ./scripts/call_rds_mssql.py list-instances
```

### 2. 查看实例详情
```bash
uv run ./scripts/call_rds_mssql.py describe-instance --instance-id mssql-xxx
```

### 3. 查看实例的账号
```bash
uv run ./scripts/call_rds_mssql.py describe-db-accounts --instance-id mssql-xxx
```

### 4. 查看实例参数配置
```bash
uv run ./scripts/call_rds_mssql.py list-parameters --instance-id mssql-xxx
```

### 5. 创建实例前查询网络信息
```bash
# 先查询 VPC
uv run ./scripts/call_rds_mssql.py list-vpcs

# 再查询子网
uv run ./scripts/call_rds_mssql.py list-subnets --vpc-id vpc-xxx --zone-id cn-beijing-a
```


## 环境变量配置

1. 获取火山引擎访问凭证：参考 [用户指南](https://www.volcengine.com/docs/6291/65568?lang=zh) 获取 AK/SK

2. 配置以下环境变量:

```bash
export VOLCENGINE_ACCESS_KEY="your-access-key"
export VOLCENGINE_SECRET_KEY="your-secret-key"
export VOLCENGINE_REGION="cn-beijing"  # 可选，默认 cn-beijing
```
