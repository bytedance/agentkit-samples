---
name: byted-bytehouse-hybrid-search
description: ByteHouse 混合检索 Skill，支持全文检索 + 向量检索，结合 RRF 重排算法实现更精准的检索结果。当用户需要在ByteHouse数据库中进行全文检索 + 向量检索，结合 RRF 重排算法实现更精准的检索结果时，使用此Skill。
version: 1.0.0
---

# ByteHouse 混合检索 Skill

## 🚀 快速开始

### 环境准备

```bash
pip install clickhouse-connect volcengine-python-sdk[ark] numpy scipy
```

### 配置说明
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

执行 `scripts/export_config.sh` 把配置信息导入环境变量中
```bash
source scripts/export_config.sh
```

---

## 📚 核心能力

### 1. 文本向量化
基于豆包文本向量化模型生成文本向量，支持任意长度中文文本。

### 2. 双索引构建
| 索引类型 | 说明 | 适用场景 |
|----------|------|----------|
| **全文倒排索引** | 基于BM25算法的全文检索，支持关键词匹配 | 精准关键词召回 |
| **向量索引** | 基于HNSW的向量相似度检索，支持语义匹配 | 语义相似召回 |

### 3. 核心功能
| 功能 | 方法 | 说明 |
|------|------|------|
| 全文检索 | `fulltext_search()` | 基于BM25的全文检索，返回BM25分数 |
| 向量检索 | `vector_search()` | 基于余弦相似度的向量检索，返回相似度分数 |
| 混合检索+RRF重排 | `hybrid_search()` | 双路召回后使用RRF算法重排，返回最终结果 |
| 自动生成向量 | `insert_document()`/`batch_insert_documents()` | 插入文档时自动生成向量并存储，无需手动处理 |
| 单个文档向量更新 | `update_document_embedding()` | 为单个文档重新生成并更新向量 |
| 批量补全缺失向量 | `batch_update_missing_embeddings()` | 自动扫描表中所有缺少向量的文档，批量生成并补全向量 |

### 4. RRF重排算法
Reciprocal Rank Fusion 算法，综合全文检索和向量检索的排名结果，公式：
```
score = Σ 1 / (k + rank)
```
默认k=60，可自定义调整。

---

## 📖 代码实现

完整示例代码实现位于 `scripts/` 目录：

- [`scripts/embedding.py`](scripts/embedding.py) - 文本向量化模块
- [`scripts/hybrid_search_client.py`](scripts/hybrid_search_client.py) - ByteHouse 混合检索客户端
- [`scripts/examples.py`](scripts/examples.py) - 使用示例
- [`scripts/export_config.sh`](scripts/export_config.sh) - 把配置文件中的信息导入环境变量

### 快速使用

```python
from scripts import ByteHouseHybridSearch

# 初始化客户端
search = ByteHouseHybridSearch(connection_type="http")

# 创建混合检索表（自动构建全文索引和向量索引）
search.create_hybrid_table("my_hybrid_index")

# 插入文档（自动生成向量 + 存储原始文本）
search.insert_document("my_hybrid_index", doc_id=1, 
                      title="ByteHouse 混合检索", 
                      content="ByteHouse 支持全文检索和向量检索，可实现混合检索能力")

# 混合检索（自动执行全文+向量检索，RRF重排返回结果）
results = search.hybrid_search("my_hybrid_index", query="ByteHouse检索能力", top_k=10)
```

---

## ⚙️ 最佳实践

### 建表配置
```sql
CREATE TABLE {table_name} (
    `doc_id` UInt64,
    `title` String,
    `content` String,
    `embedding` Array(Float32),
    -- 全文倒排索引（version=2支持BM25分数）
    INDEX content_idx content TYPE inverted('standard', '{"version":"v4"}') GRANULARITY 1,
    -- 向量索引（HNSW算法，余弦相似度）
    INDEX embedding_idx embedding TYPE HNSW_SQ('DIM={vec_dimensions}', 'metric=COSINE', 'M=32', 'EF_CONSTRUCTION=256') GRANULARITY 1
)
ENGINE = CnchMergeTree()
ORDER BY doc_id
SETTINGS 
    index_granularity = 1024,
    enable_vector_index_preload = 1
```

### RRF参数调整
- 当全文检索结果更重要时，可降低`rrf_k`值（推荐30-60）
- 当向量检索结果更重要时，可提高`rrf_k`值（推荐60-100）


## 🔗 参考文档

- [ByteHouse 全文检索文档](https://www.volcengine.com/docs/6464/1208708)
- [ByteHouse 向量检索文档](https://www.volcengine.com/docs/6464/1208707)
- [RRF算法论文](https://plg.uwaterloo.ca/~gvcormac/cormackpapers/trec03cormack.pdf)
