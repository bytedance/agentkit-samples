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
ByteHouse 混合检索客户端
支持全文检索、向量检索、RRF重排
"""
import os
import clickhouse_connect
from typing import List, Dict, Optional, Any
from embedding import MultimodalEmbedding

class ByteHouseHybridSearch:
    def __init__(self,
                 host: Optional[str] = None,
                 port: Optional[int] = None,
                 user: Optional[str] = None,
                 password: Optional[str] = None,
                 database: Optional[str] = None,
                 secure: Optional[bool] = None,
                 connection_type: str = "http"):
        """
        初始化ByteHouse客户端
        :param host: ByteHouse地址，默认从环境变量BYTEHOUSE_HOST读取
        :param port: ByteHouse端口，默认从环境变量BYTEHOUSE_PORT读取
        :param user: 用户名，默认从环境变量BYTEHOUSE_USER读取
        :param password: 密码，默认从环境变量BYTEHOUSE_PASSWORD读取
        :param database: 默认数据库，默认从环境变量BYTEHOUSE_DATABASE读取，默认default
        :param secure: 是否启用加密，默认从环境变量BYTEHOUSE_SECURE读取，默认True
        :param connection_type: 连接类型，http或native，默认http
        """
        self.host = host or os.getenv("BYTEHOUSE_HOST")
        self.port = port or int(os.getenv("BYTEHOUSE_PORT", "8123"))
        self.user = user or os.getenv("BYTEHOUSE_USER", "bytehouse")
        self.password = password or os.getenv("BYTEHOUSE_PASSWORD")
        self.database = database or os.getenv("BYTEHOUSE_DATABASE", "default")
        self.secure = secure if secure is not None else (os.getenv("BYTEHOUSE_SECURE", "true").lower() == "true")
        
        if not self.host or not self.password:
            raise ValueError("请配置BYTEHOUSE_HOST和BYTEHOUSE_PASSWORD环境变量")
        
        # 初始化ByteHouse连接
        self.client = clickhouse_connect.get_client(
            host=self.host,
            port=self.port,
            username=self.user,
            password=self.password,
            database=self.database,
            secure=self.secure,
            verify=False,
            connect_timeout=30,
            send_receive_timeout=60
        )
        
        # 初始化向量化客户端
        self.dimensions = int(os.environ.get("EMBEDDING_DIMENSIONS", 2048))
        self.embedding_client = MultimodalEmbedding()
    
    def create_hybrid_table(self, table_name: str, if_not_exists: bool = True) -> None:
        """
        创建混合检索表，自动构建全文倒排索引和向量索引
        :param table_name: 表名
        :param if_not_exists: 是否存在就跳过，默认True
        """
        exists_clause = "IF NOT EXISTS" if if_not_exists else ""
        vec_dimensions = self.dimensions
        # 兼容旧版本ByteHouse，先创建基础表，索引可后续手动添加
        create_sql = f"""
        CREATE TABLE {exists_clause} {table_name} (
            `doc_id` UInt64,
            `title` String,
            `content` String,
            `embedding` Array(Float32),
            `create_time` DateTime DEFAULT now(),
            INDEX content_idx content TYPE inverted('standard', '{{\"version\":\"v4\"}}') GRANULARITY 1,
            INDEX embedding_idx embedding TYPE HNSW_SQ('DIM={vec_dimensions}', 'metric=COSINE', 'M=32', 'EF_CONSTRUCTION=256') GRANULARITY 1
        )
        ENGINE = CnchMergeTree()
        ORDER BY doc_id
        SETTINGS
            index_granularity = 1024,
            enable_vector_index_preload = 1
        """
        self.client.command(create_sql)
        print(f"混合检索表 {table_name} 创建成功，向量维度：{vec_dimensions}")
    
    def insert_document(self, table_name: str, doc_id: int, title: str, content: str) -> None:
        """
        插入单个文档
        :param table_name: 表名
        :param doc_id: 文档ID
        :param title: 文档标题
        :param content: 文档内容
        """
        # 拼接标题和内容生成向量
        full_text = f"标题：{title} 内容：{content}"
        embedding = self.embedding_client.encode_text(full_text)
        
        insert_sql = f"""
        INSERT INTO {table_name} (doc_id, title, content, embedding)
        VALUES (%s, %s, %s, %s)
        """
        self.client.command(insert_sql, parameters=[doc_id, title, content, embedding])
    
    def batch_insert_documents(self, table_name: str, documents: List[Dict[str, Any]]) -> None:
        """
        批量插入文档
        :param table_name: 表名
        :param documents: 文档列表，每个元素包含doc_id, title, content字段
        """
        # 构建插入数据
        data = []
        for doc in documents:
            # 逐个生成向量
            full_text = f"标题：{doc['title']} 内容：{doc['content']}"
            emb = self.embedding_client.encode_text(full_text)
            
            # 验证向量维度正确性
            if len(emb) != self.dimensions:
                raise ValueError(f"向量维度错误：期望{self.dimensions}维，实际{len(emb)}维")
            
            data.append([
                doc['doc_id'],
                doc['title'],
                doc['content'],
                emb
            ])
        
        for row in data:
            self.client.command(f"INSERT INTO {table_name} (doc_id, title, content, embedding) VALUES (%s, %s, %s, %s)", parameters=row)
        print(f"成功插入 {len(documents)} 条文档，向量已自动生成并写入")
    
    def fulltext_search(self, table_name: str, query: str, top_k: int = 20) -> List[Dict[str, Any]]:
        """
        全文检索，基于BM25算法
        :param table_name: 表名
        :param query: 查询关键词
        :param top_k: 返回结果数量，默认20
        :return: 检索结果，包含doc_id, title, content, bm25_score字段
        """
        query_escaped = self.transform_string(query)
        search_sql = f"""
        SELECT 
            doc_id, 
            title, 
            content,
            _text_search_score as bm25_score
        FROM {table_name}
        WHERE textSearch(content, '{query_escaped}')
        ORDER BY bm25_score DESC
        LIMIT {top_k}
        """
        print(f"执行全文检索查询：{search_sql}")
        results = self.client.query(search_sql).result_rows
        return [
            {
                "doc_id": row[0],
                "title": row[1],
                "content": row[2],
                "bm25_score": float(row[3])
            }
            for row in results
        ]
    
    def vector_search(self, table_name: str, query: str, top_k: int = 20) -> List[Dict[str, Any]]:
        """
        向量检索，基于余弦相似度
        :param table_name: 表名
        :param query: 查询文本
        :param top_k: 返回结果数量，默认20
        :return: 检索结果，包含doc_id, title, content, vector_score字段
        """
        # 生成查询向量
        query_embedding = self.embedding_client.encode_text(query)
        
        search_sql = f"""
        SELECT 
            doc_id, 
            title, 
            content,
            cosineDistance(embedding, %s) as vector_score
        FROM {table_name}
        ORDER BY vector_score ASC
        LIMIT {top_k}
        """
        print(f"执行向量检索查询：{search_sql}")
        results = self.client.query(search_sql, parameters=[query_embedding]).result_rows
        return [
            {
                "doc_id": row[0],
                "title": row[1],
                "content": row[2],
                "vector_score": float(row[3])
            }
            for row in results
        ]
    
    def rrf_rerank(self, 
                   fulltext_results: List[Dict[str, Any]], 
                   vector_results: List[Dict[str, Any]], 
                   top_k: int = 10,
                   rrf_k: int = 60) -> List[Dict[str, Any]]:
        """
        RRF重排算法，融合全文检索和向量检索结果
        :param fulltext_results: 全文检索结果
        :param vector_results: 向量检索结果
        :param top_k: 返回重排后的结果数量，默认10
        :param rrf_k: RRF算法k参数，默认60
        :return: 重排后的结果，包含rrf_score字段
        """
        # 构建文档分数字典
        doc_scores: Dict[int, Dict[str, Any]] = {}
        
        # 处理全文检索结果
        for rank, result in enumerate(fulltext_results):
            doc_id = result["doc_id"]
            if doc_id not in doc_scores:
                doc_scores[doc_id] = result.copy()
                doc_scores[doc_id]["rrf_score"] = 0.0
            # 累加RRF分数
            doc_scores[doc_id]["rrf_score"] += 1.0 / (rrf_k + rank + 1)
        
        # 处理向量检索结果
        for rank, result in enumerate(vector_results):
            doc_id = result["doc_id"]
            if doc_id not in doc_scores:
                doc_scores[doc_id] = result.copy()
                doc_scores[doc_id]["rrf_score"] = 0.0
            # 累加RRF分数
            doc_scores[doc_id]["rrf_score"] += 1.0 / (rrf_k + rank + 1)
        
        # 按RRF分数排序
        sorted_docs = sorted(doc_scores.values(), key=lambda x: x["rrf_score"], reverse=True)
        
        # 返回top_k结果
        return sorted_docs[:top_k]
    
    def hybrid_search(self, 
                      table_name: str, 
                      query: str, 
                      top_k: int = 10,
                      recall_k: int = 20,
                      rrf_k: int = 60) -> List[Dict[str, Any]]:
        """
        混合检索：全文+向量双路召回 + RRF重排
        :param table_name: 表名
        :param query: 查询文本
        :param top_k: 返回最终结果数量，默认10
        :param recall_k: 每路召回数量，默认20
        :param rrf_k: RRF算法k参数，默认60
        :return: 最终检索结果
        """
        # 两路召回
        fulltext_results = self.fulltext_search(table_name, query, top_k=recall_k)
        vector_results = self.vector_search(table_name, query, top_k=recall_k)
        
        # RRF重排
        reranked_results = self.rrf_rerank(fulltext_results, vector_results, top_k=top_k, rrf_k=rrf_k)
        
        return reranked_results
    
    def close(self) -> None:
        """关闭连接"""
        self.client.close()

    def transform_string(self, s: str) -> str:
        # Remove all single quotes
        s = s.replace("'", "")
        s = s.replace(" ", "")
        
        # Split each character with |
        return "|".join(s)
