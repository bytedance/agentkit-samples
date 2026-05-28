---
name: byted-bytehouse-ai-query
description: ByteHouse AI 查询技能，支持自然语言转SQL（Text2SQL）、SQL执行、表结构查询、多模态向量化和向量检索，用于ByteHouse数据库的自然语言查询、SQL生成与执行。
version: 1.0.0
---

# byted-bytehouse-ai-query

## 描述

ByteHouse AI Query Skill，提供 Text2SQL 接口能力，支持将自然语言转换为 SQL 并执行查询。

**核心能力**：
1. **Text2SQL** - 将自然语言描述的查询需求转换为 ByteHouse SQL 语句
2. **List Tables** - 列出数据库中的表
3. **Execute SQL** - 执行 SQL 查询并返回结果
4. **多模态向量化** - 支持文本、图片、视频的向量化存储和混合检索

## 📁 文件说明

- **SKILL.md** - 本文件，技能主文档
- **init_config.py** - 初始化配置文件脚本
- **text2sql.py** - Text2SQL 转换脚本
- **list_tables.py** - 列出数据库中的表
- **execute_sql.py** - 执行 SQL 查询脚本
- **embedding.py** - 多模态向量化脚本
- **search_client.py** - 向量检索客户端脚本(使用ByteHouse向量检索)
- **export_config.sh** - 配置导出环境变量脚本（从~/.bytehouse_config.json读取）

把这个文档也发给客户，文档里面介绍了如何获取主机地址和密码：https://www.volcengine.com/docs/6517/1121919?lang=zh 

## 配置说明
配置保存在 `~/.bytehouse_config.json` ，如果该文件存在且非空，则直接使用文件中的配置。如果不存在，则让用户提供ByteHouse连接信息（ 把这个文档也发给客户，文档里面介绍了如何获取主机地址和密码：https://www.volcengine.com/docs/6517/1121919?lang=zh ）。用户提供信息后，保存到json文件，避免重复向用户请求连接信息。当用户切换ByteHouse集群时，一并修改该文件。

```json
{
   "BYTEHOUSE_HOST": "<ByteHouse-host>",
   "BYTEHOUSE_PORT": "8123",
   "BYTEHOUSE_USER": "bytehouse",
   "BYTEHOUSE_PASSWORD": "<ByteHouse-password>",
   "BYTEHOUSE_SECURE": true,
   "BYTEHOUSE_VERIFY": true, 
   "BH_ARK_API_KEY": "<火山引擎方舟API密钥>",
   "BH_ARK_BASE_URL": "https://ark.cn-beijing.volces.com/api/v3",
   "BH_EMBEDDING_MODEL": "doubao-embedding-vision-251215"
}
```
其中BYTEHOUSE_HOST（主机地址）和BYTEHOUSE_PASSWORD（密码）**必须由**用户提供。BH_ARK_API_KEY为可选配置，仅在embedding时使用，用户初次使用时可忽略。其余配置固定。

## 使用限制
1. 风险预警：如果Text2SQL生成的SQL不是DQL类型（例如 INSERT/UPDATE/DROP 等 DML/DDL），AI助手**必须首先阻断执行**，向用户展示生成的具体SQL，并明确询问用户是否确认执行。
   - 当作为AI助手调用 `execute_sql.py` 执行非DQL时，脚本会默认报错并提示需要确认。
   - 只有在用户明确同意执行后，AI助手才可以通过在调用命令中附加 `--force` 参数（例如 `python3 scripts/execute_sql.py "DROP TABLE xxx" --force`）来强制执行。
2. 结果呈现：默认展示前5条符合查询条件的结果，如果返回异常，展示具体的报错信息
3. 用户询问任何数据或者资产相关的问题，总是执行SQL查询后返回结果，不要根据上下文猜答案
4. 不要直接输出敏感信息，如密码、Key等，确实需要输出时，需要Mask处理


## 前置条件

- Python 3.8+
- uv (已安装在 `/root/.local/bin/uv`)
- ByteHouse连接信息（保存在`~/.bytehouse_config.json`，如果不存在，让用户先提供）

## 🚀 快速开始

### 1. 把ByteHouse连接信息导出到环境变量

```bash
# 从配置文件读取配置，导出到环境变量
source scripts/export_config.sh
```

### 2. 列出数据库和表

```bash
# 列出所有数据库
python3 scripts/list_tables.py --databases

# 列出指定数据库的表
python3 scripts/list_tables.py --database tpcds
```

### 3. 使用 Text2SQL

```bash
# 执行 Text2SQL
python3 scripts/text2sql.py "get count of all call centers" "tpcds.call_center"
```

返回：
```sql
SELECT COUNT(*) AS call_center_count FROM tpcds.call_center;
```

### 4. 执行 SQL 查询

```bash
python3 scripts/execute_sql.py "SELECT * FROM tpcds.call_center LIMIT 5"
python3 scripts/execute_sql.py "SELECT count(*) FROM tpcds.store_sales" --format pretty
```

### 5. 完整流程：Text2SQL + Execute

```bash
# 1. 先获取 SQL
SQL=$(python3 text2sql.py "get count of call centers" "tpcds.call_center")

# 2. 执行 SQL
python3 scripts/execute_sql.py "$SQL"
```

### 6. 多模态向量化

需要向量化多模态内容（文本、图片、视频），请使用以下脚本：
- [`scripts/embedding.py`](scripts/embedding.py) - 多模态向量化模块
- [`scripts/multimodal_search_client.py`](scripts/multimodal_search_client.py) - ByteHouse 检索客户端

```python
from scripts import ByteHouseMultimodalSearch

# 初始化客户端
search = ByteHouseMultimodalSearch(connection_type="http")

# 创建表
search.create_multimodal_table("my_index")

# 插入文档
search.insert_document("my_index", doc_id=1, content_type="text", 
                      content="ByteHouse 多模态检索", title="介绍")

# 向量检索（需要过滤0维向量，否则会报错）
query_embedding = search.embedding.encode_text("云原生数据仓库")
results = search.vector_search("my_index", query_embedding=query_embedding, top_k=10)
```

🔗 参考文档

- [ByteHouse 向量检索SQL文档](https://www.volcengine.com/docs/6464/1208707)
- [火山引擎多模态向量化API文档](https://www.volcengine.com/docs/82379/1409291)



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
