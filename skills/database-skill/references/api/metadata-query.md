---
name: "metadata-query-api"
description: "元数据探查与数据查询函数的参数、返回格式、数据库类型差异速查。"
---

# 元数据探查与数据查询 API

## 数据库类型兼容性

| 函数 | MySQL | VeDB-MySQL | Postgres | SQL Server | MongoDB | Redis |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| `list_instances` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `list_databases` | ✓ | ✓ | ✓ | ✓ | ⚠️ 仅总数 | ✗ |
| `list_tables` | ✓ | ✓ | ✓ 需 schema | ✓ | ⚠️ 仅总数 | ✗ |
| `get_table_info` | ✓ | ✓ | ✓ SQL 回退 | ✓ | ✗ | ✗ |
| `nl2sql` | ✓ | ✓ | ✓ | ✓ | ⚠️ Pipeline | ✗ |
| `execute_sql` | ✓ SQL | ✓ SQL | ✓ SQL | ✓ SQL | ✓ Mongo 语法 | ✓ Redis 命令 |
| `query_sql` | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |

**说明**：
- `✗` 表示不支持（调用时代码会自动拦截并返回错误）。`instance_type` 由代码自动解析，无需手动传递。
- **MongoDB `execute_sql`**：使用 Mongo 语法（如 `db.getCollectionNames()`、`db.collection.find({})`），不支持 SQL。
- **Redis `execute_sql`**：使用 Redis 命令（如 `INFO server`、`GET key`），`database` 参数须传数字（0-15）。
- **MongoDB `list_databases`/`list_tables`**：API 返回 `total` 计数但 Items 为 null（DBW 后端 bug），暂无法获取明细列表。可通过 `execute_sql` 执行 `db.getCollectionNames()` 替代。
- **MongoDB `nl2sql`**：生成 Pipeline 而非 SQL，必须通过 `tables` 参数指定一个 collection 名，准确率较低。
- **External 实例**（`instance_id` 以 `External-` 开头）：元数据和 SQL 查询正常，但不支持运维诊断和监控 API。

---

> **调用前提**：
> ```python
> cd skills/database-skill/scripts && python3 -c "
> from toolbox import create_client, <函数名>
> client = create_client(region='cn-beijing')  # 可选参数见下方 create_client 说明
> result = <函数名>(client, ...)
> print(result)
> "
> ```
>
> **`create_client` 参数**（均可选，不传时从环境变量读取）：
> | 参数 | 说明 |
> |:---|:---|
> | `region` | 地域，如 `"cn-beijing"`。环境变量 `VOLCENGINE_REGION` |
> | `instance_id` | 默认实例 ID。环境变量 `VOLCENGINE_INSTANCE_ID` |
> | `database` | 默认数据库名。环境变量 `VOLCENGINE_DATABASE` |
>
> 下方函数签名中 `client` 参数类型为 `ToolboxClient`（即 `create_client()` 返回值）。

## 元数据函数

### list_instances

查询实例列表。**必须传过滤项**，不传等于查全量，无意义。

```python
list_instances(client,        # ToolboxClient: create_client() 返回值
    instance_id=None,     # str: 按实例 ID 搜索
    query=None,           # str: 模糊搜索（不确定是 ID 还是名称时用这个）
    instance_name=None,   # str: 按实例名称搜索
    ds_type=None,         # str: MySQL | Postgres | Mongo | Redis | MSSQL | VeDBMySQL | External
    instance_status=None, # str: 状态过滤
    page_number=1,        # int
    page_size=10,         # int
)
```

**返回** `data`:
- `total`: 匹配总数
- `instances[]`: 实例列表
  - `id`, `name`, `status`, `type`（实例类型）, `version`, `region`, `zone`, `create_time`
  - 托管实例额外字段：`endpoint`, `port`, `cpu`, `memory`, `storage`
  - **External 实例**（`id` 以 `External-` 开头）：无连接信息字段，DBW 代理连接

### list_databases

列出实例下的数据库。

```python
list_databases(client,        # ToolboxClient: create_client() 返回值
    instance_id=None,    # str: 不传则用 create_client() 默认值
    page_number=1,       # int
    page_size=10,        # int
)
```

**返回** `data`:
- `total`, `page`
- `databases[]`: `name`, `charset`, `collation`, `is_system`, `description`

### list_tables

列出数据库中的表。

```python
list_tables(client,           # ToolboxClient: create_client() 返回值
    instance_id=None,    # str
    database=None,       # str
    schema=None,         # str: Postgres 必传（默认查 public）
    page_number=1,       # int
    page_size=50,        # int
    fetch_all=False,     # bool: True 时自动翻页获取全部表
)
```

**返回** `data`:
- `total`, `database`, `schema`（如有）
- `tables[]`: 表/集合列表

**数据库差异**：
- **Postgres**: 必须通过 `schema` 参数指定 schema，不传默认查 `public`
- **MongoDB**: 返回的是集合（collection）列表
- **Redis**: 不支持

### get_table_info

获取表结构（列名、类型、注释等）。

```python
get_table_info(client,        # ToolboxClient: create_client() 返回值
    table="表名",        # str: 必传
    instance_id=None,    # str
    database=None,       # str
    schema=None,         # str: Postgres 需要
)
```

**返回** `data`:
- `name`, `engine`, `charset`, `definition`
- `columns[]`: `name`, `type`, `length`, `nullable`, `primary_key`, `auto_increment`, `default`, `comment`

**数据库差异**：
- **Postgres**: 自动使用 SQL 回退（查 `information_schema.columns`），无法获取主键和自增信息
- **MongoDB**: 不支持（无固定 schema）
- **Redis**: 不支持

---

## 数据查询函数

### nl2sql

自然语言转 SQL（仅生成，不执行）。

```python
nl2sql(client,                # ToolboxClient: create_client() 返回值
    query="自然语言问题",  # str: 必传
    instance_id=None,     # str
    database=None,        # str
    tables=None,          # list[str]: 指定参考表名，提升准确率
)
```

**最佳实践**：先 `list_tables` 获取表名，传入 `tables` 参数缩小范围。生成的 SQL 可能有字段名偏差，需要校验后再执行。

**数据库差异**：
- **MongoDB**: 生成 Pipeline 而非 SQL，准确率较低
- **Redis**: 不支持

### execute_sql

执行查询。MySQL / VeDB / PG / SQLServer 使用 SQL，MongoDB 使用 Mongo 语法，Redis 使用 Redis 命令。

```python
execute_sql(client,           # ToolboxClient: create_client() 返回值
    sql="SELECT ...",    # str: 必传（MongoDB 传 Mongo 语法，Redis 传 Redis 命令）
    instance_id=None,    # str
    database=None,       # str（Redis 须传数字 0-15）
)
```

**返回** `data`:
- `sql`, `state`, `row_count`, `columns[]`, `rows[]`（每行是 `{列名: 值}` 字典）

**限制**：
- 最多返回 **3000 行**，超出静默截断。返回恰好 3000 行 = 数据被截断，需用 `SELECT COUNT(*)` 获取真实计数
- INSERT / UPDATE / DELETE / DDL 会被拦截，必须走工单

**数据库差异**：
- **Postgres**: SQL 中表名需用 `schema.table` 写法（如 `public.users`）
- **MongoDB**: 使用 Mongo 语法（如 `db.getCollectionNames()`、`db.collection.find({})`）
- **Redis**: 使用 Redis 命令（如 `INFO server`、`GET key`），`database` 参数须传数字（0-15）

### query_sql

执行 SQL 返回 pandas DataFrame，是 `execute_sql` 的便捷封装。

```python
query_sql(client,             # ToolboxClient: create_client() 返回值
    sql="SELECT ...",    # str: 必传
    instance_id=None,    # str
    database=None,       # str
)
```

**返回**: `pandas.DataFrame`（成功时）或 `{"success": False, ...}` 字典（失败时）

同样受 3000 行截断限制。适合需要后续用 pandas 分析的场景。

**数据库差异**：
- **MongoDB / Redis**: 不支持（无法转为 DataFrame）。MongoDB 可用 `execute_sql` 获取数据后导出为 JSON/CSV 再用 `MultiSourceAnalyzer` 分析。
