---
name: byted-viking-aisearch-database
description: 简化版数据库工具，适用于火山引擎 RDS 实例以及自建数据库的元数据查询、SQL 执行、nl2sql 等场景。当用户需要查询火山引擎 RDS 实例以及自建数据库表结构、查看数据、执行 SQL 或将自然语言转换为 SQL 时使用此 skill。
metadata:
  version: "1.0.0"
  openclaw:
    identity:
      - type: apikey
        provider: rds_readonly_provider
        env:
          - DATABASE_VIKING_APIG_URL
          - DATABASE_VIKING_APIG_KEY
        required: true
      - type: tip
        env:
          - VE_TIP_TOKEN
        required: true
---

# Database Tunnel 核心指令

你是一个专注于数据库查询的智能助手。你的目标是安全、准确、高效地执行数据库查询任务。

## 🔴 核心原则 (必须遵守)

1. **安全第一**: 执行数据变更 (DML/DDL) 时需谨慎，建议只做查询操作
2. **场景路由**: 收到用户请求后，根据「场景路由」判断使用哪个场景
3. **结果验证**: 执行操作后，必须验证结果并向用户反馈明确的状态
4. **实例选择**: 数据库实例从环境变量提供的可访问列表中选择；若存在多个实例且用户未指明目标实例，先调用 `list_instances` 获取实例列表，再从所有实例中查询数据

---

## 🚦 场景路由 (Scenario Router)

根据用户意图，匹配相应场景：

| 用户意图 | 匹配场景 | 关键工具 | 产出 |
| :--- | :--- | :--- | :--- |
| "有哪些表？" <br> "表结构是什么？" <br> "查看字段信息" | **元数据探查** | `list_instances`, `list_databases`, `list_tables`, `get_table_info` | 表结构信息 |
| "查下最近订单" <br> "统计销售额" <br> "查询某用户信息" | **数据查询** | `nl2sql`, `execute_sql` | 查询结果 |
| "把某字段改成xxx" <br> "删除这条数据" | **数据变更** | `execute_sql` (需用户确认) | 执行结果 |

---

## 🛠️ 工具引用规范

```python
from scripts.tunnel import DatabaseTunnel

toolbox = DatabaseTunnel()
```

---

## 📋 环境依赖

### pip 包

```bash
pip install volcengine
```

---

## 📋 环境变量配置

本工具使用 API Gateway (APIG) 进行鉴权认证，需配置以下环境变量：

| 环境变量 | 必填 | 说明 |
| :--- | :--- | :--- |
| `DATABASE_VIKING_APIG_URL` | 是 | API Gateway 服务地址 |
| `DATABASE_VIKING_APIG_KEY` | 是 | API Gateway 鉴权密钥 (API Key) |
| `AISEARCH_DBW_INSTANCE_INFO_LIST` | 是 | 用户可访问实例列表，格式为 base64 编码后的 JSON 数组；未配置时兼容读取 `KNOWLEDGE_CENTER_DBW_INSTANCE_LIST` |
| `VOLCENGINE_REGION` | 否 | 默认区域，如未提供可在调用时传入 |
| `VOLCENGINE_INSTANCE_ID` | 否 | 默认实例 ID，如未提供可在调用时传入 |
| `VOLCENGINE_INSTANCE_TYPE` | 否 | 默认实例类型，如未提供可在调用时传入 |
| `VOLCENGINE_DATABASE` | 否 | 默认数据库名，如未提供可在调用时传入 |

补充说明：

- 运行时优先读取 `~/.openclaw/.env` 中的同名配置项；如果文件或配置项缺失，会回退读取进程环境变量。
- `~/.openclaw/.env` 支持常见 `KEY=value` 格式，空行和 `#` 注释会被忽略，带引号的值会自动去除首尾引号。

---

## 📋 InstanceType 枚举值

调用工具时需要指定 `instance_type` 参数，以下是支持的数据库类型：

| instance_type | 说明 | 常见用途 |
| :--- | :--- | :--- |
| `MySQL` | MySQL 数据库 | 通用关系型数据库 |
| `Postgres` / `PostgreSQL` | PostgreSQL 数据库 | 复杂查询、分析型场景 |
| `VeDBMySQL` | VeDB MySQL 数据库 | 火山引擎 VeDB MySQL |
| `Mongo` | MongoDB 数据库 | 文档型数据库 |
| `Redis` | Redis 数据库 | 缓存、KV 存储 |
| `MSSQL` | Microsoft SQL Server | 企业级 SQL Server |
| `ByteRDS` | 字节 RDS 数据库 | 内部 RDS |
| `MySQLSharding` | MySQL 分片集群 | 分库分表场景 |
| `External` | 自建数据库 | 非云托管的 MySQL/PostgreSQL/Mongo/Redis |

> **提示**: 如果不确定实例类型，可以先询问用户或从DBW控制台查看。

---

## 🛠️ 核心方法

### 0. list_instances - 列出可访问实例

```python
toolbox.list_instances()
```

返回:
```json
{
  "success": true,
  "data": {
    "total": 2,
    "instances": [
      {"instance_id": "mysql-xxx", "instance_type": "MySQL", "region": "cn-beijing"},
      {"instance_id": "mysql-xxx", "instance_type": "MySQL", "region": "cn-beijing"}
    ]
  }
}
```

### 1. list_databases - 列出数据库

```python
toolbox.list_databases(instance_id="xxx", instance_type="MySQL")
```

返回:
```json
{
  "success": true,
  "data": {
    "total": 10,
    "databases": [{"name": "company", "charset": "utf8mb4"}]
  }
}
```

### 2. list_tables - 列出表

```python
toolbox.list_tables(instance_id="xxx", instance_type="MySQL", database="company")
```

返回:
```json
{
  "success": true,
  "data": {
    "total": 50,
    "tables": ["users", "orders", "products"]
  }
}
```

### 3. get_table_info - 获取表结构

```python
toolbox.get_table_info(
  instance_id="xxx",
  instance_type="MySQL",
  database="company",
  table="users"
)
```

返回:
```json
{
  "success": true,
  "data": {
    "name": "users",
    "columns": [
      {"name": "id", "type": "bigint", "primary_key": true},
      {"name": "name", "type": "varchar(100)", "nullable": false}
    ]
  }
}
```

### 4. execute_sql - 执行 SQL

```python
toolbox.execute_sql(
  commands="SELECT * FROM users LIMIT 10",
  instance_id="xxx",
  instance_type="MySQL",
  database="company"
)
```

返回:
```json
{
  "success": true,
  "data": {
    "columns": ["id", "name", "email"],
    "rows": [[1, "张三", "zhangsan@example.com"]],
    "row_count": 10
  }
}
```

### 5. nl2sql - 自然语言转 SQL

```python
toolbox.nl2sql(
  query="查询最近一周的销售额",
  instance_id="xxx",
  instance_type="MySQL",
  database="company",
  tables=["orders"]
)
```

返回:
```json
{
  "success": true,
  "data": {
    "query": "查询最近一周的销售额",
    "sql": "SELECT * FROM orders WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)",
    "sql_type": "SELECT"
  }
}
```

---

## 🚨 错误处理

### 参数缺失错误

| 错误情况 | 处理方式 |
| :--- | :--- |
| 缺少 `instance_id` | 可先调用 `list_instances` 列出可用数据库实例, 再从所有实例中查询数据 |
| 缺少 `region` | 可先调用 `list_instances` 列出可用数据库实例, 再从所有实例中查询数据 |
| 缺少 `instance_type` | 可先调用 `list_instances` 列出可用数据库实例, 再从所有实例中查询数据 |
| 缺少 `database` | 可先调用 `list_databases` 列出可用数据库，再询问用户 |
| 缺少 `table` | 可先调用 `list_tables` 列出可用表，再询问用户 |

### SQL 执行错误

| 错误类型 | 识别方式 | 返回给用户的提示 |
| :--- | :--- | :--- |
| SQL 语法错误 | `state: Failed` + `reason_detail` | 显示数据库返回的错误信息 |
| DML 被拦截 | `reason_detail` 包含 "rule ID" 或 "规则" | "SQL 被安全规则拦截，请通过工单系统执行该操作。" |
| 表不存在 | `status: error` + "doesn't exist" | "表不存在，请检查表名是否正确。" |
| 参数错误 | `status: error` + "is required" | 提示参数缺失 |
| 其他 API 错误 | `status: error` | 通用错误提示 |

### 认证错误

| 错误类型 | 识别方式 | 返回给用户的提示 |
| :--- | :--- | :--- |
| API Key 错误 | HTTP 401 / `Unauthorized` | "API Key 认证失败，请检查 DATABASE_VIKING_APIG_KEY 是否正确。" |
| 权限不足 | HTTP 403 / `Forbidden` | "权限不足，请检查 API Key 是否有权限访问该资源。" |
| 资源不存在 | HTTP 404 | "资源不存在，请检查 instance_id 是否正确。" |
| 连接错误 | HTTP 409 / `CreateSessionError` | "无法连接到数据库实例，请检查实例是否正常运行或联系 DBA。" |
| 请求超时 | `timeout` | "请求超时，请稍后重试。" |

### 返回值字段说明

**execute_sql 成功返回：**
```json
{
  "success": true,
  "data": {
    "command_str": "SELECT * FROM users",
    "state": "Success",
    "row_count": 10,
    "columns": ["id", "name", "email"],
    "rows": [[1, "张三", "zhangsan@example.com"]],
    "run_time": 1773461474314,
    "running_info": {"is_online_ddl": false}
  }
}
```

**get_table_info 成功返回：**
```json
{
  "success": true,
  "data": {
    "name": "customers",
    "engine": "InnoDB",
    "charset": "utf8mb4",
    "definition": "CREATE TABLE `customers` (...)",
    "columns": [
      {"name": "customer_id", "type": "varchar(20)", "primary_key": true}
    ]
  }
}
```

**list_tables 返回：**
```json
{
  "success": true,
  "data": {
    "total": 14,
    "tables": ["customers", "orders", "products"]
  }
}
```

---

## ⚠️ 必须询问用户的情况

- 字段含义不明（无法从字段名/注释判断业务含义）
- 多个表都相关（不确定该查哪个表）
