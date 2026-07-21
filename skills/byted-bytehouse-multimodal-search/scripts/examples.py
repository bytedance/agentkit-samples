# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
使用示例代码
"""

# ==================== 示例1: 初始化客户端 ====================
"""
from search_client import ByteHouseMultimodalSearch

# 方式1：HTTP连接（默认，适合大多数场景）
search = ByteHouseMultimodalSearch(
    connection_type="http",
    secure=True,
    compress="zstd"
)

# 方式2：TCP连接（适合高并发、大数据量写入）
search = ByteHouseMultimodalSearch(
    connection_type="tcp",
    connect_timeout=300,
    send_receive_timeout=1000
)
"""

# ==================== 示例2: 创建多模态检索表 ====================
"""
search.create_multimodal_table(
    table_name="multimodal_index",
    enable_text_search=True,
    index_type="HNSW",
    metric="COSINE"
)
"""

# ==================== 示例3: 插入数据 ====================
"""
# 插入文本
search.insert_document(
    table_name="multimodal_index",
    doc_id=1,
    content_type="text",
    content="ByteHouse 是火山引擎推出的云原生数据仓库",
    title="ByteHouse 介绍",
    metadata={"category": "文档"}
)

# 插入图片
search.insert_document(
    table_name="multimodal_index",
    doc_id=2,
    content_type="image",
    content="https://example.com/image.jpg",
    title="架构图",
    metadata={"category": "图片"}
)

# 批量插入
documents = [
    {"doc_id": 3, "content_type": "text", "content": "向量检索能力", "title": "功能介绍"},
    {"doc_id": 4, "content_type": "image", "content": "https://example.com/img2.jpg", "title": "示意图"}
]
result = search.insert_batch_documents(
    table_name="multimodal_index",
    documents=documents
)
print(f"成功插入 {result['success_count']} 条")
"""

# ==================== 示例4: 向量检索 ====================
"""
query_embedding = search.embedding.encode_text("云原生数据仓库")
results = search.vector_search(
    table_name="multimodal_index",
    query_embedding=query_embedding,
    top_k=5
)
"""

# ==================== 示例5: 以文搜图 ====================
"""
results = search.text_search_image(
    table_name="multimodal_index",
    query_text="ByteHouse 架构图",
    top_k=3
)
"""

# ==================== 示例6: 以图搜图 ====================
"""
results = search.image_search_image(
    table_name="multimodal_index",
    image_url="https://example.com/query-image.jpg",
    top_k=5
)
"""

# ==================== 示例7: 混合检索 ====================
"""
results = search.hybrid_search(
    table_name="multimodal_index",
    query_text="ByteHouse 视频教程",
    top_k=5,
    vector_weight=0.6,
    text_weight=0.4
)
"""

# ==================== 示例8: 带条件过滤的检索 ====================
"""
results = search.text_search_image(
    table_name="multimodal_index",
    query_text="架构图",
    top_k=5,
    filter_condition="create_time >= now() - INTERVAL 7 DAY"
)
"""
