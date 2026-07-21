---
name: byted-bytehouse-multimodal-search
description: ByteHouse 多模态检索 Skill，支持文本、图片、视频的向量化存储与多模态混合检索（向量检索、以文搜图、以图搜文、混合关键词 + 向量检索）。当用户提到 "ByteHouse 向量检索"、"多模态检索"、"混合检索"、"以文搜图"、"以图搜图"、"文搜视频"、"多模态知识库"、"HNSW / 向量索引" 等诉求时使用本 Skill。
version: 1.0.1
---

# ByteHouse 多模态检索 Skill

## 描述

本 Skill 基于 ByteHouse 的向量检索能力和火山引擎方舟多模态向量化模型（默认 `doubao-embedding-vision`），提供从**向量化 → 建表 → 写入 → 检索**的一整套多模态检索参考实现。核心能力：

1. **多模态向量化**：文本 / 图片 / 视频 → 统一维度向量。
2. **向量表创建**：支持 HNSW、IVF_FLAT、IVF_PQ 等索引，可选启用全文倒排索引。
3. **文档写入**：单条 / 批量插入，附带 `content_type`、`title`、`metadata`。
4. **检索能力**：向量检索、混合检索（向量 + 关键词）、以文搜图、以图搜图 / 视频。

**当以下情况时使用此 Skill：**

1. 用户希望在 ByteHouse 中搭建多模态向量检索服务。
2. 用户需要对已有多模态数据（文本、图片、视频）进行向量化后写入 ByteHouse。
3. 用户提到 "向量检索"、"多模态检索"、"混合检索"、"以文搜图"、"以图搜视频" 等关键词。

## 前置条件

- Python 3.8+
- Python 依赖：`clickhouse-connect`、`clickhouse-driver`（TCP 场景）、`volcengine-python-sdk[ark]`、`numpy`
  ```bash
  pip install clickhouse-connect clickhouse-driver "volcengine-python-sdk[ark]" numpy
  ```
- `jq`（`export_config.sh` 依赖，解析 JSON 配置。安装方式：`brew install jq` 或 `sudo apt install jq`）
- 有效的 ByteHouse 连接信息与方舟 API Key（保存于 `~/.bytehouse_config.json`）

## 📁 文件说明

- **SKILL.md** — 本文件，技能主文档。
- **scripts/embedding.py** — 多模态向量化模块（`MultimodalEmbedding`）。
- **scripts/search_client.py** — ByteHouse 多模态检索客户端（`ByteHouseMultimodalSearch`）。
- **scripts/examples.py** — 常见调用示例（初始化、建表、写入、检索）。
- **scripts/__init__.py** — Python 包入口，暴露 `MultimodalEmbedding` 与 `ByteHouseMultimodalSearch`。
- **scripts/export_config.sh** — 从 `~/.bytehouse_config.json` 加载配置到环境变量（依赖 `jq`）。

## 🧭 智能体使用指引

1. **确认配置**：`source scripts/export_config.sh`，让 `BYTEHOUSE_*`、`BH_ARK_*` 等环境变量就绪。
2. **确认场景**：向用户澄清是要 "建表 + 写入" 还是 "只做检索"，以及数据模态（纯文本 / 文本 + 图片 / 视频等）。
3. **选择索引策略**：
   - 数据量 < 100 万：`HNSW` + `COSINE`（默认）。
   - 数据量较大或希望更省内存：`HNSW_SQ` / `IVF_FLAT` / `IVF_PQ`。
4. **建表 + 写入**：调用 `ByteHouseMultimodalSearch.create_multimodal_table(...)`、`insert_document(...)` 或 `batch_insert(...)`。
5. **检索**：优先使用 `vector_search(...)` 或 `hybrid_search(...)`，返回结果会自动过滤掉零向量、异常数据。
6. **安全提示**：`BH_ARK_API_KEY`、`BYTEHOUSE_PASSWORD` 等凭据只写入 `~/.bytehouse_config.json`，不要打印到日志或消息里。

## 配置说明

配置保存在 `~/.bytehouse_config.json`。如果文件存在且非空，直接使用；否则，让用户提供 ByteHouse 连接信息与方舟 API Key（可以把 [ByteHouse 连接信息获取指引](https://www.volcengine.com/docs/6517/1121919?lang=zh) 一并发给用户），拿到后写入 JSON 文件，避免重复询问。当用户切换 ByteHouse 集群或方舟账号时，一并更新该文件。

```json
{
   "BYTEHOUSE_HOST": "<ByteHouse-host>",
   "BYTEHOUSE_PORT": "8123",
   "BYTEHOUSE_USER": "bytehouse",
   "BYTEHOUSE_PASSWORD": "<ByteHouse-password>",
   "BYTEHOUSE_DATABASE": "default",
   "BH_ARK_API_KEY": "<火山引擎方舟 API 密钥>",
   "BH_ARK_BASE_URL": "https://ark.cn-beijing.volces.com/api/v3",
   "BH_EMBEDDING_MODEL": "doubao-embedding-vision-251215",
   "EMBEDDING_DIMENSIONS": "2048"
}
```

- `BYTEHOUSE_HOST`（主机地址）与 `BYTEHOUSE_PASSWORD`（密码）**必须由用户提供**。
- 其它字段建议保留默认值。
- **运行前必须**通过 `source scripts/export_config.sh` 把配置导出到环境变量：`search_client.py` 与 `embedding.py` 只从环境变量读取配置。

```bash
source scripts/export_config.sh
```

## 🚀 快速开始

### 1. 初始化客户端

```python
import sys, os
# 把 scripts/ 目录加入 sys.path
SKILL_SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts")
sys.path.insert(0, SKILL_SCRIPTS_DIR)

from search_client import ByteHouseMultimodalSearch

search = ByteHouseMultimodalSearch(connection_type="http")
```

### 2. 创建多模态检索表

```python
search.create_multimodal_table(
    table_name="multimodal_index",
    enable_text_search=True,
    index_type="HNSW",
    metric="COSINE",
)
```

### 3. 写入数据

```python
# 文本
search.insert_document(
    "multimodal_index",
    doc_id=1,
    content_type="text",
    content="ByteHouse 是火山引擎推出的云原生数据仓库",
    title="ByteHouse 介绍",
    metadata={"category": "文档"},
)

# 图片（自动生成向量）
search.insert_document(
    "multimodal_index",
    doc_id=2,
    content_type="image",
    content="https://example.com/image.jpg",
    title="示例图片",
)
```

### 4. 向量检索

```python
# 文本查询 → 向量检索
query_embedding = search.embedding.encode_text("云原生数据仓库")
results = search.vector_search(
    "multimodal_index",
    query_embedding=query_embedding,
    top_k=10,
)

# 混合检索（关键词 + 向量）
results = search.hybrid_search(
    "multimodal_index",
    query_text="云原生数据仓库",
    top_k=10,
)
```

更多示例参见 [`scripts/examples.py`](scripts/examples.py)。

## 支持的索引类型

| 索引类型 | 说明 | 参数 |
|----------|------|------|
| HNSW | 高性能通用索引 | M, EF_CONSTRUCTION |
| HNSW_SQ | HNSW 标量量化，节省内存 | M, EF_CONSTRUCTION |
| IVF_FLAT | 倒排文件索引 | dim, metric |
| IVF_PQ | 乘积量化 | dim, metric |
| IVF_PQ_FS | PQ 快速搜索 | dim, metric |

## 支持的向量化输入

- **文本**：任意字符串。
- **图片**：URL 或 base64 编码。
- **视频**：URL 或 base64 编码（帧采样 + 向量化）。

## 失败兜底建议

| 现象 | 处理方式 |
|------|----------|
| `ModuleNotFoundError: volcenginesdkarkruntime` | 让用户安装 `pip install "volcengine-python-sdk[ark]"`。 |
| `BH_ARK_API_KEY` 未设置 | 引导用户在方舟控制台申请 API Key 并写入 `~/.bytehouse_config.json`。 |
| `BYTEHOUSE_HOST` / `BYTEHOUSE_PASSWORD` 未设置 | 引导用户提供连接信息，写入 `~/.bytehouse_config.json` 后 `source scripts/export_config.sh`。 |
| 返回结果为空向量 / 全 0 向量 | 客户端已经过滤零向量；若仍频繁出现，检查向量化输入格式（URL 是否可访问、图片是否损坏）。 |
| 建表报错 "index type xxx not supported" | 让用户确认集群版本，或改用 `HNSW` 兜底。 |

## 参考文档

- [ByteHouse 向量检索 SQL 文档](https://www.volcengine.com/docs/6464/1208707)
- [火山引擎方舟多模态向量化 API 文档](https://www.volcengine.com/docs/82379/1409291)
