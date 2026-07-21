---
name: byted-bytehouse-ai-query
description: ByteHouse AI 查询技能，提供自然语言转 SQL（Text2SQL）、SQL 执行、库表结构查询、多模态向量化和向量检索等能力，覆盖 ByteHouse 云数仓的日常查询、SQL 生成与执行场景。当用户提到 "ByteHouse"、"查表"、"查数据"、"Text2SQL"、"自然语言查询"、"列出数据库"、"列出表"、"执行 SQL"、"生成 SQL"、"多模态检索" 等诉求，或者需要基于 ByteHouse 完成上述任务时，应使用本 Skill。
version: 1.0.1
---

# byted-bytehouse-ai-query

## 描述

ByteHouse AI Query Skill，提供以下核心能力：

1. **Text2SQL** — 将自然语言查询需求转换为 ByteHouse SQL。
2. **List Tables** — 列出目标数据库/实例下的所有库与表。
3. **Execute SQL** — 执行 SQL 查询并返回结果，内置非 DQL 保护。
4. **多模态向量化与检索** — 支持文本、图片、视频的向量化，以及向量/混合检索。

**当以下情况时使用此 Skill：**
1. 用户希望通过自然语言查询 ByteHouse 中的数据（"帮我查一下 xxx 表数据量"、"看看有哪些库和表" 等）。
2. 用户明确要求把自然语言转成 SQL（Text2SQL），或需要在 ByteHouse 上执行 SQL。
3. 用户希望在 ByteHouse 上进行文本/图片/视频的向量化存储与检索。
4. 用户提到 ByteHouse、火山引擎云数仓、云原生数仓、数据仓库查询相关关键词。

## 🧭 智能体使用指引（重要）

Agent 在承接上述任务时，按以下流程调度本 Skill 内的脚本：

1. **确保配置就绪**：先执行 `source scripts/export_config.sh`，把 `~/.bytehouse_config.json` 中的配置注入环境变量。
   - 若 `~/.bytehouse_config.json` 不存在或缺失 `BYTEHOUSE_HOST` / `BYTEHOUSE_PASSWORD`，主动引导用户提供，并把用户返回的连接信息写入该 JSON 文件后再 `source`。
2. **摸清数据全貌**：若用户没有明确指定库表，先使用 `scripts/list_tables.py` 查询数据库/表列表，帮助用户/Agent 选定要查的表。
3. **生成 SQL**：需要把自然语言转成 SQL 时，使用 `scripts/text2sql.py`，将目标表以位置参数传入。
4. **执行 SQL**：拿到 SQL 后使用 `scripts/execute_sql.py`。默认只允许执行 DQL，非 DQL（INSERT/UPDATE/DROP 等）需要先向用户确认再附加 `--force`。
5. **多模态检索场景**：使用 `scripts/embedding.py` + `scripts/search_client.py` 完成向量化与向量/混合检索。
6. **展示结果**：默认返回前 5 条结果，异常时展示完整报错。任何时候都要对密钥、密码等敏感字段做 Mask。

Agent **必须**通过上述脚本发起查询/执行，不允许自行拼装 SQL 或直接连接 ByteHouse。

## 📁 文件说明

- **SKILL.md** — 本文件，技能主文档。
- **requirements.txt** — Python 依赖列表。
- **scripts/text2sql.py** — Text2SQL 转换脚本。
- **scripts/list_tables.py** — 列出数据库或指定库下的表。
- **scripts/execute_sql.py** — 执行 SQL 查询脚本，内置 DQL 保护。
- **scripts/client.py** — ByteHouse 连接客户端通用模块。
- **scripts/embedding.py** — 多模态向量化脚本。
- **scripts/search_client.py** — ByteHouse 向量检索客户端。
- **scripts/export_config.sh** — 从 `~/.bytehouse_config.json` 加载配置到环境变量（依赖 `jq`）。

## 配置说明

配置文件位于 `~/.bytehouse_config.json`。如果文件存在且非空，直接使用文件中的配置；否则，向用户询问必填连接信息（可以把这份文档发给用户以便查阅 [ByteHouse 连接信息获取指引](https://www.volcengine.com/docs/6517/1121919?lang=zh)），拿到后写入 JSON 文件，避免重复询问。当用户切换 ByteHouse 集群时，一并更新该文件。

```json
{
   "BYTEHOUSE_HOST": "<ByteHouse-host>",
   "BYTEHOUSE_PORT": "8123",
   "BYTEHOUSE_USER": "bytehouse",
   "BYTEHOUSE_PASSWORD": "<ByteHouse-password>",
   "BH_ARK_API_KEY": "<火山引擎方舟 API 密钥>",
   "BH_ARK_BASE_URL": "https://ark.cn-beijing.volces.com/api/v3",
   "BH_EMBEDDING_MODEL": "doubao-embedding-vision-251215"
}
```

- `BYTEHOUSE_HOST`（主机地址）与 `BYTEHOUSE_PASSWORD`（密码）**必须由用户提供**。
- `BH_ARK_API_KEY` 只在多模态向量化时使用，其余场景可忽略。
- 其它字段建议保留默认值。

## 使用限制

1. **非 DQL 保护**：若 Text2SQL 生成的 SQL 属于 INSERT / UPDATE / DELETE / DROP 等 DML / DDL 语句，Agent **必须先阻断执行**，向用户展示具体 SQL 并明确询问是否确认。
   - `execute_sql.py` 遇到非 DQL 时默认报错并要求确认。
   - 只有用户明确同意后，才可以附加 `--force` 参数强制执行，例如：
     ```bash
     python3 scripts/execute_sql.py "DROP TABLE xxx" --force
     ```
2. **结果呈现**：默认展示前 5 条符合查询条件的结果，异常时展示完整报错信息。
3. **禁止臆测**：对于数据 / 资产相关的问题，一律走 SQL 执行后再回答，不要基于上下文猜答案。
4. **敏感信息保护**：不要直接输出密码、Key 等敏感信息，如确需展示应做 Mask。

## 前置条件

- Python 3.8+
- `jq`（`export_config.sh` 解析 JSON 需要，未安装时可 `brew install jq` 或 `sudo apt install jq`）
- Python 依赖：见 [`requirements.txt`](requirements.txt)，可通过 `pip install -r requirements.txt` 安装
- 有效的 ByteHouse 连接信息（保存于 `~/.bytehouse_config.json`）

## 🚀 快速开始

### 1. 加载 ByteHouse 连接信息

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

### 3. Text2SQL

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
# 1. 生成 SQL
SQL=$(python3 scripts/text2sql.py "get count of call centers" "tpcds.call_center")

# 2. 执行 SQL
python3 scripts/execute_sql.py "$SQL"
```

### 6. 多模态向量化与检索

多模态相关脚本：

- [`scripts/embedding.py`](scripts/embedding.py) — 多模态向量化模块
- [`scripts/search_client.py`](scripts/search_client.py) — ByteHouse 向量检索客户端

```python
# 从脚本目录调用，或将 scripts/ 加入 sys.path
from search_client import ByteHouseMultimodalSearch

# 初始化客户端
search = ByteHouseMultimodalSearch(connection_type="http")

# 创建表
search.create_multimodal_table("my_index")

# 插入文档
search.insert_document(
    "my_index",
    doc_id=1,
    content_type="text",
    content="ByteHouse 多模态检索",
    title="介绍",
)

# 向量检索（返回结果中已过滤掉 0 维向量）
query_embedding = search.embedding.encode_text("云原生数据仓库")
results = search.vector_search("my_index", query_embedding=query_embedding, top_k=10)
```

参考文档：

- [ByteHouse 向量检索 SQL 文档](https://www.volcengine.com/docs/6464/1208707)
- [火山引擎多模态向量化 API 文档](https://www.volcengine.com/docs/82379/1409291)

## 💻 程序化调用

### Text2SQL + Execute 一体化

```python
import subprocess
import json


def ai_query(natural_language: str, tables: list, config: dict = None) -> str:
    """调用 Text2SQL 并执行查询"""
    cmd = ["python3", "scripts/text2sql.py", natural_language] + tables
    if config:
        cmd.extend(["--config", json.dumps(config)])

    sql_result = subprocess.run(cmd, capture_output=True, text=True)
    sql = sql_result.stdout.strip()

    if not sql:
        return f"Text2SQL failed: {sql_result.stderr}"

    result = subprocess.run(
        ["python3", "scripts/execute_sql.py", sql],
        capture_output=True,
        text=True,
    )
    return result.stdout


if __name__ == "__main__":
    print(ai_query("get count of call centers", ["tpcds.call_center"]))
```

## API 参考

### Text2SQL 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| systemHints | string | 否 | 系统提示词，默认为 "TEXT2SQL" |
| input | string | **是** | 自然语言查询 |
| knowledgeBaseIDsString | string[] | 否 | 知识库 ID 列表，默认 ["*"] |
| tables | string[] | **是** | 要查询的表名列表 |
| config | object | 否 | 自定义配置 |
| config.reasoningModel | string | 否 | 自定义模型 ID |
| config.reasoningAPIKey | string | 否 | 自定义 API Key |
| config.url | string | 否 | 自定义 API URL |
