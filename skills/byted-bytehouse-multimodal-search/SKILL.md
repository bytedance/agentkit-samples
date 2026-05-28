---
name: byted-bytehouse-multimodal-search
description: ByteHouse 多模态检索 Skill，支持文本、图片、视频的向量化存储和混合检索。当用户需要在ByteHouse数据库中进行多模态向量化存储和混合检索时，使用此Skill。
version: 1.0.0
---

# ByteHouse 多模态检索 Skill

## 🚀 快速开始

### 环境准备

```bash
pip install clickhouse-connect volcengine-python-sdk[ark] numpy
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

### 1. 多模态向量化

基于豆包多模态向量化模型 `doubao-embedding-vision-251215`：

| 输入类型 | 支持格式 | 最大限制 |
|----------|----------|----------|
| **文本** | 纯文本字符串 | 无长度限制 |
| **图片** | JPG/PNG/GIF/WEBP/BMP | <10MB，宽高>14px |
| **视频** | MP4/AVI/MOV | <50MB |

**关键约束**：
- 多模态向量化必须调用 `/embeddings/multimodal` 接口
- 图片/视频输入格式：`{"type": "image_url", "image_url": {"url": "xxx"}}`
- 部分模型不支持 `dimensions` 参数

### 2. 向量检索功能

| 功能 | 方法 | 说明 |
|------|------|------|
| 纯向量检索 | `vector_search()` | 基于向量相似度检索 |
| 混合检索 | `hybrid_search()` | 向量+全文检索融合 |
| 以文搜图 | `text_search_image()` | 文本搜索图片 |
| 以图搜图 | `image_search_image()` | 图片搜索相似图片 |
| 以文搜视频 | `text_search_video()` | 文本搜索视频 |

---

## 📖 代码实现

完整示例代码实现位于 `scripts/` 目录：

- [`scripts/embedding.py`](scripts/embedding.py) - 多模态向量化模块
- [`scripts/search_client.py`](scripts/search_client.py) - ByteHouse 检索客户端
- [`scripts/examples.py`](scripts/examples.py) - 使用示例
- [`scripts/export_config.sh`](scripts/export_config.sh) - 把配置文件中的信息导入环境变量

### 快速使用

```python
from scripts import ByteHouseMultimodalSearch

# 初始化客户端
search = ByteHouseMultimodalSearch(connection_type="http")

# 创建表
search.create_multimodal_table("my_index")

# 插入文档
search.insert_document("my_index", doc_id=1, content_type="text", 
                      content="ByteHouse 多模态检索", title="介绍")

# 向量检索
results = search.vector_search("my_index", query_embedding=embedding, top_k=10)
```

---

## ⚙️ 最佳实践

### 索引选择

| 数据规模 | 索引类型 | 适用场景 |
|----------|----------|----------|
| <100万 | HNSW | 中小规模，低延迟 |
| 100万-1亿 | HNSW_SQ | 大规模，平衡性能成本 |
| >1亿 | IVF_PQ_FS | 超大规模 |

### 性能优化

```sql
SETTINGS 
    index_granularity = 1024,
    index_granularity_bytes = 0,
    enable_vector_index_preload = 1
```

### 指令优化

| 场景 | Query 侧指令 |
|------|--------------|
| 通用文搜图 | `Target_modality: image. Instruction:根据文本描述找到对应的图片.` |
| 电商商品检索 | `Target_modality: image. Instruction:找到和描述匹配的同款商品图片.` |
| 原图检索 | `Target_modality: image. Instruction:查找和本图完全相同的图片.` |

---

## ❓ 常见问题

**Q1: 向量维度怎么选？**
- 推荐 2048 维作为通用值
- 维度越高精度越高，但成本也越高

**Q2: 如何处理低召回问题？**
1. 增大 `hnsw_ef_s` 参数


**Q3: API 调用失败排查**
- **404**: 检查路径是否为 `/embeddings/multimodal`
- **400**: 检查输入格式，部分模型不支持 `dimensions`
- **401**: 检查 `ARK_API_KEY` 是否正确
- **429**: 降低请求频率

---

## 🔗 参考文档

- [ByteHouse 向量检索SQL文档](https://www.volcengine.com/docs/6464/1208707)
- [火山引擎多模态向量化API文档](https://www.volcengine.com/docs/82379/1409291)
