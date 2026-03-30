---
name: byted-bytehouse-ai-query
description: ByteHouse AI Query Skill，提供 Text2SQL 接口能力，支持将自然语言转换为 SQL 并执行查询。当用户需要将自然语言查询转换为 SQL、查询 ByteHouse 数据库，或提到 text2sql、自然语言转 SQL、AI查询时使用此 Skill。
compatibility: Requires Python 3.8+, uv, and ByteHouse connection information
---

# byted-bytehouse-ai-query

## 描述

ByteHouse AI Query Skill，提供 Text2SQL 接口能力，支持将自然语言转换为 SQL 并执行查询。

**核心能力**：
1. **Text2SQL** - 将自然语言描述的查询需求转换为 ByteHouse SQL 语句
2. **List Tables** - 列出数据库中的表
3. **Execute SQL** - 执行 SQL 查询并返回结果

## 📁 文件说明

- **SKILL.md** - 本文件，技能主文档
- **text2sql.py** - Text2SQL 转换脚本
- **list_tables.py** - 列出数据库中的表
- **execute_sql.py** - 执行 SQL 查询脚本

## 前置条件

- Python 3.8+
- uv (已安装在 `/root/.local/bin/uv`)
- ByteHouse连接信息（需自行配置环境变量）

## 配置信息

### ByteHouse连接配置

```bash
# 基础配置
export BYTEHOUSE_HOST="<ByteHouse主机>"      # 如 tenant-xxx-cn-beijing-public.bytehouse.volces.com
export BYTEHOUSE_PASSWORD="<密码>"            # 用作 Bearer token (Text2SQL)
export BYTEHOUSE_USER="<用户名>"              # 用于执行 SQL
export BYTEHOUSE_PORT="<端口>"                # 默认 8123
```

## 🚀 快速开始

### 1. 列出数据库和表

```bash
# 列出所有数据库
python3 list_tables.py --databases

# 列出指定数据库的表 (默认 tpcds)
python3 list_tables.py --database tpcds
```

### 2. 使用 Text2SQL

```bash
# 环境变量方式
export BYTEHOUSE_HOST="tenant-xxx-cn-beijing-public.bytehouse.volces.com"
export BYTEHOUSE_PASSWORD="<your-password>"

# 执行 Text2SQL
python3 text2sql.py "get count of all call centers" "tpcds.call_center"
```

返回：
```sql
SELECT COUNT(*) AS call_center_count FROM tpcds.call_center;
```

### 3. 执行 SQL 查询

```bash
python3 execute_sql.py "SELECT * FROM tpcds.call_center LIMIT 5"
python3 execute_sql.py "SELECT count(*) FROM tpcds.store_sales" --format pretty
```

### 4. 完整流程：Text2SQL + Execute

```bash
# 1. 先获取 SQL
SQL=$(python3 text2sql.py "get count of call centers" "tpcds.call_center")

# 2. 执行 SQL
python3 execute_sql.py "$SQL"
```

## 💻 程序化调用

### Text2SQL + Execute 一体化

```python
import subprocess
import json

def ai_query(natural_language: str, tables: list, config: dict = None) -> str:
    """
    调用 Text2SQL 并执行查询
    
    Args:
        natural_language: 自然语言描述
        tables: 要查询的表名列表
        config: 可选的配置 dict
    
    Returns:
        查询结果
    """
    # 1. 获取 SQL
    cmd = ["python3", "text2sql.py", natural_language] + tables
    if config:
        cmd.extend(["--config", json.dumps(config)])
    
    sql_result = subprocess.run(cmd, capture_output=True, text=True)
    sql = sql_result.stdout.strip()
    
    if not sql:
        return f"Text2SQL failed: {sql_result.stderr}"
    
    # 2. 执行 SQL
    result = subprocess.run(
        ["python3", "execute_sql.py", sql],
        capture_output=True,
        text=True
    )
    
    return result.stdout

# 使用示例
result = ai_query("get count of call centers", ["tpcds.call_center"])
print(result)
```

## API 参考

### Text2SQL 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| systemHints | string | 否 | 系统提示词，默认为 "TEXT2SQL" |
| input | string | **是** | 自然语言查询 |
| knowledgeBaseIDsString | string[] | 否 | 知识库ID列表，默认 ["*"] |
| tables | string[] | **是** | 要查询的表名列表 |
| config | object | 否 | 自定义配置 |
| config.reasoningModel | string | 否 | 自定义模型ID |
| config.reasoningAPIKey | string | 否 | 自定义 API Key |
| config.url | string | 否 | 自定义 API URL |
