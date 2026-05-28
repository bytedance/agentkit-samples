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
ByteHouse 混合检索使用示例
"""
from hybrid_search_client import ByteHouseHybridSearch

def main():
    # 初始化客户端
    search = ByteHouseHybridSearch(host="",
                                   user="",
                                   password="",
                                   database="",
                                   connection_type="")
    
    table_name = "demo_hybrid_index"
    
    print("=== 清理旧表 ===")
    search.client.command(f"DROP TABLE IF EXISTS {table_name}")
    
    # 1. 创建混合检索表
    print("=== 创建混合检索表 ===")
    search.create_hybrid_table(table_name, if_not_exists=True)
    
    # 2. 插入测试数据
    print("\n=== 插入测试数据 ===")
    documents = [
        {
            "doc_id": 1,
            "title": "ByteHouse 全文检索",
            "content": "ByteHouse 企业版支持全文检索能力，基于倒排索引实现，支持BM25相似度计算，可快速检索文本内容。"
        },
        {
            "doc_id": 2,
            "title": "ByteHouse 向量检索",
            "content": "ByteHouse 支持向量检索功能，基于HNSW索引实现，支持余弦相似度、L2距离等多种相似度计算方式。"
        },
        {
            "doc_id": 3,
            "title": "混合检索最佳实践",
            "content": "结合全文检索和向量检索的优势，使用RRF重排算法可以实现更精准的检索效果，兼顾关键词匹配和语义匹配。"
        },
        {
            "doc_id": 4,
            "title": "RRF重排算法",
            "content": "RRF（Reciprocal Rank Fusion）是一种常用的多路召回融合算法，通过对不同召回源的排名进行加权融合，得到最终的排序结果。"
        },
        {
            "doc_id": 5,
            "title": "ClickHouse 二级索引",
            "content": "ClickHouse 支持二级索引功能，包括跳数索引、全文倒排索引、向量索引等，可大幅提升查询性能。"
        }
    ]
    search.batch_insert_documents(table_name, documents)
    print("测试数据插入完成")
    
    # 3. 全文检索示例
    print("\n=== 全文检索示例，查询：'ByteHouse 检索' ===")
    fulltext_results = search.fulltext_search(table_name, query="ByteHouse 检索", top_k=3)
    for i, res in enumerate(fulltext_results):
        print(f"排名 {i+1}: [doc_id={res['doc_id']}] {res['title']}，BM25分数：{res['bm25_score']:.4f}")
        print(f"内容摘要：{res['content'][:50]}...\n")
    
    # 4. 向量检索示例
    print("\n=== 向量检索示例，查询：'怎么实现更好的检索效果' ===")
    vector_results = search.vector_search(table_name, query="怎么实现更好的检索效果", top_k=3)
    for i, res in enumerate(vector_results):
        print(f"排名 {i+1}: [doc_id={res['doc_id']}] {res['title']}，向量相似度：{res['vector_score']:.4f}")
        print(f"内容摘要：{res['content'][:50]}...\n")
    
    # 5. 混合检索+RRF重排示例
    print("\n=== 混合检索+RRF重排示例，查询：'ByteHouse 检索效果优化' ===")
    hybrid_results = search.hybrid_search(table_name, query="ByteHouse 检索效果优化", top_k=3)
    for i, res in enumerate(hybrid_results):
        print(f"排名 {i+1}: [doc_id={res['doc_id']}] {res['title']}，RRF分数：{res['rrf_score']:.4f}")
        if 'bm25_score' in res:
            print(f"BM25分数：{res['bm25_score']:.4f}")
        if 'vector_score' in res:
            print(f"向量相似度：{res['vector_score']:.4f}")
        print(f"内容摘要：{res['content'][:80]}...\n")
    
    # 关闭连接
    search.close()

if __name__ == "__main__":
    main()
