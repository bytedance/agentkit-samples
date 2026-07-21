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
ByteHouse 多模态检索客户端
支持向量检索、混合检索、以文搜图、以图搜图等功能
"""

import os
import json
from typing import List, Dict, Any

from embedding import MultimodalEmbedding



class ByteHouseMultimodalSearch:
    """ByteHouse多模态检索客户端"""
    
    def __init__(self,
                 connection_type: str = "http",
                 secure: bool = True,
                 compress: str = "zstd",
                 connect_timeout: int = 300,
                 send_receive_timeout: int = 1000):
        """
        初始化ByteHouse多模态检索客户端

        Args:
            connection_type: 连接方式，可选 http/tcp
            secure: 是否启用加密连接
            compress: 压缩方式，可选 zstd/lz4/False
            connect_timeout: 连接超时时间，单位秒
            send_receive_timeout: 请求超时时间，单位秒
        """
        self.connection_type = connection_type
        self.dimensions = int(os.environ.get("EMBEDDING_DIMENSIONS", 2048))
        self.embedding = MultimodalEmbedding()

        host = os.environ.get("BYTEHOUSE_HOST", "") or ""

        # 使用原生驱动连接 ByteHouse
        if connection_type == "http":
            import clickhouse_connect
            self.client = clickhouse_connect.get_client(
                host=host,
                port=int(os.environ.get("BYTEHOUSE_PORT", 8123)),
                username=os.environ.get("BYTEHOUSE_USER", "bytehouse"),
                password=os.environ.get("BYTEHOUSE_PASSWORD"),
                database=os.environ.get("BYTEHOUSE_DATABASE") or None,
                secure=secure,
                verify=False,
                compress=compress,
                send_receive_timeout=send_receive_timeout,
            )
        elif connection_type == "tcp":
            from clickhouse_driver import Client
            self.client = Client(
                host=host,
                port=int(os.environ.get("BYTEHOUSE_PORT", 9000)),
                user=os.environ.get("BYTEHOUSE_USER", "bytehouse"),
                password=os.environ.get("BYTEHOUSE_PASSWORD"),
                database=os.environ.get("BYTEHOUSE_DATABASE", "default"),
                connect_timeout=connect_timeout,
                send_receive_timeout=send_receive_timeout,
                compression=compress if compress else False,
                secure=secure,
                client_revision=54430,
            )
        else:
            raise ValueError(f"不支持的连接类型: {connection_type}")
    
    
    def _check_dql(self, sql: str, force: bool = False):
        """检查SQL是否为DQL，如果不是则要求确认"""
        import sys
        sql_upper = sql.strip().upper()
        is_dql = any(sql_upper.startswith(prefix) for prefix in ("SELECT", "SHOW", "DESC", "DESCRIBE", "EXPLAIN", "WITH", "CREATE"))
        
        if not is_dql and not force:
            if sys.stdin.isatty():
                confirm = input(f"警告: 检测到非DQL查询:\n{sql}\n是否确认执行？(y/N): ")
                if confirm.lower() not in ['y', 'yes']:
                    print("已取消执行。", file=sys.stderr)
                    sys.exit(0)
            else:
                print("Error: 这是一个非DQL查询（如INSERT/UPDATE/DROP等）。作为AI助手，请立即中断执行，并向用户明确询问是否确认执行此操作（展示出具体的SQL）。如果用户明确同意，请在调用时传递 force=True 参数再次执行。", file=sys.stderr)
                sys.exit(1)

    def _execute_sql(self, sql: str, query_type: str = "select", force: bool = False):
        """内部通用SQL执行方法，直接使用原生驱动执行 SQL"""
        self._check_dql(sql, force)
        try:
            if query_type == "select":
                result = self.client.query(sql)
                return result.result_rows if hasattr(result, 'result_rows') else result
            else:
                return self.client.command(sql)

        except Exception as e:
            error_msg = str(e).lower()
            if "connection" in error_msg or "timeout" in error_msg:
                raise ConnectionError(f"数据库连接异常：{e}")
            elif "syntax" in error_msg or "parse" in error_msg:
                raise ValueError(f"SQL语法错误：{e}")
            elif "permission" in error_msg or "auth" in error_msg:
                raise PermissionError(f"权限不足：{e}")
            else:
                raise Exception(f"数据库操作失败：{e}")
    
    def create_multimodal_table(self, 
                               table_name: str,
                               enable_text_search: bool = True,
                               index_type: str = "HNSW",
                               metric: str = "COSINE",
                               hnsw_m: int = 32,
                               hnsw_ef_construction: int = 512,
                               force: bool = False):
        """
        创建多模态检索表
        
        Args:
            table_name: 表名
            enable_text_search: 是否开启全文检索
            index_type: 索引类型，可选 HNSW/HNSW_SQ/IVF_FLAT/IVF_PQ/IVF_PQ_FS
            metric: 距离度量，可选 COSINE/L2
            hnsw_m: HNSW 每个节点最大连接数
            hnsw_ef_construction: HNSW 构建时探索因子
        """
        if index_type in ["HNSW", "HNSW_SQ"]:
            index_config = f"TYPE {index_type}('DIM={self.dimensions}, METRIC={metric}, M={hnsw_m}, EF_CONSTRUCTION={hnsw_ef_construction}')"
        else:
            index_config = f"TYPE {index_type}('dim={self.dimensions}', 'metric={metric}')"
        
        text_index = f"INDEX text_idx (title, content) TYPE inverted('standard', '{{\"version\":\"v4\"}}')" if enable_text_search else ""
        
        create_sql = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id UInt64 COMMENT '唯一ID',
            content_type Enum('text' = 1, 'image' = 2, 'video' = 3) COMMENT '内容类型',
            content String COMMENT '原始内容或URL',
            title String COMMENT '标题/描述',
            embedding Array(Float32) COMMENT '向量',
            CONSTRAINT cons_vec_len CHECK length(embedding) = {self.dimensions},
            metadata Map(String, String) COMMENT '元数据',
            create_time DateTime DEFAULT now() COMMENT '创建时间',
            INDEX vec_idx embedding {index_config},
            {text_index}
        ) ENGINE = CnchMergeTree
        ORDER BY id
        SETTINGS 
            index_granularity = 1024,
            index_granularity_bytes = 0,
            enable_vector_index_preload = 1
        """
        
        self._execute_sql(create_sql, query_type="ddl", force=True)
    
    def insert_document(self,
                       table_name: str,
                       doc_id: int,
                       content_type: str,
                       content: str,
                       title: str = "",
                       metadata: Dict = None,
                       embedding: List[float] = None,
                       instruction: str = None) -> bool:
        """插入单条文档"""
        if embedding is None:
            if content_type == "text":
                embedding = self.embedding.encode_text(content, instruction)
            elif content_type == "image":
                embedding = self.embedding.encode_image(content, instruction)
            elif content_type == "video":
                embedding = self.embedding.encode_video(content, instruction)
            else:
                raise ValueError(f"不支持的内容类型: {content_type}")
        
        if len(embedding) != self.dimensions:
            raise ValueError(f"向量维度错误：期望{self.dimensions}维，实际{len(embedding)}维")
        
        metadata_str = json.dumps(metadata).replace("'", "''") if metadata else "{}"
        
        insert_sql = f"""
        INSERT INTO {table_name}
        (id, content_type, content, title, embedding, metadata)
        VALUES
        ({doc_id}, '{content_type}', '{content.replace("'", "''")}', 
         '{title.replace("'", "''")}', {embedding}, '{metadata_str}')
        """
        
        self._execute_sql(insert_sql, query_type="dml", force=True)
        return True
    
    def insert_batch_documents(self,
                              table_name: str,
                              documents: List[Dict],
                              instruction: str = None,
                              skip_error: bool = True) -> Dict:
        """批量插入文档"""
        rows = []
        failed = []
        
        for idx, doc in enumerate(documents):
            try:
                required_fields = ["doc_id", "content_type", "content"]
                for field in required_fields:
                    if field not in doc:
                        raise ValueError(f"缺少必填字段: {field}")
                
                if doc.get('embedding'):
                    embedding = doc['embedding']
                    if len(embedding) != self.dimensions:
                        raise ValueError(f"向量维度错误")
                else:
                    if doc['content_type'] == "text":
                        embedding = self.embedding.encode_text(doc['content'], instruction)
                    elif doc['content_type'] == "image":
                        embedding = self.embedding.encode_image(doc['content'], instruction)
                    elif doc['content_type'] == "video":
                        embedding = self.embedding.encode_video(doc['content'], instruction)
                    else:
                        raise ValueError(f"不支持的内容类型: {doc['content_type']}")
                
                metadata = doc.get('metadata', {})
                metadata_str = json.dumps(metadata).replace("'", "''")
                
                rows.append([
                    doc['doc_id'],
                    doc['content_type'],
                    doc['content'].replace("'", "''"),
                    doc.get('title', '').replace("'", "''"),
                    embedding,
                    metadata_str
                ])
            
            except Exception as e:
                failed.append({"doc_id": doc.get("doc_id", idx), "error": str(e)})
                if not skip_error:
                    raise
        
        if rows:
            try:
                self._check_dql(f"INSERT INTO {table_name} (批量插入 {len(rows)} 条数据)", True)
                if self.connection_type == "http":
                    self.client.insert(
                        table_name,
                        rows,
                        column_names=['id', 'content_type', 'content', 'title', 'embedding', 'metadata'],
                        column_type_names=['UInt64', 'Enum', 'String', 'String', 'Array(Float32)', 'Map(String, String)']
                    )
                else:
                    self.client.execute(
                        f'INSERT INTO {table_name} VALUES',
                        rows
                    )
                success_count = len(rows)
            except Exception as e:
                for row in rows:
                    failed.append({"doc_id": row[0], "error": f"批量插入失败: {str(e)}"})
                success_count = 0
        else:
            success_count = 0
        
        return {
            "success_count": success_count,
            "failed_count": len(failed),
            "failed_details": failed
        }
    
    def vector_search(self,
                     table_name: str,
                     query_embedding: List[float],
                     top_k: int = 10,
                     filter_condition: str = None,
                     metric: str = "COSINE",
                     hnsw_ef_s: int = 200) -> List[Dict]:
        """纯向量检索"""
        distance_func = "cosineDistance" if metric == "COSINE" else "L2Distance"
        
        sql = f"""
        SELECT 
            id, content_type, content, title, metadata, create_time,
            {distance_func}(embedding, {query_embedding}) AS score
        FROM {table_name}
        {f"WHERE {filter_condition}" if filter_condition else ""}
        ORDER BY score ASC
        LIMIT {top_k}
        SETTINGS enable_new_ann = 1, hnsw_ef_s = {hnsw_ef_s}
        """
        
        rows = self._execute_sql(sql, query_type="select")
        columns = ['id', 'content_type', 'content', 'title', 'metadata', 'create_time', 'score']
        return [dict(zip(columns, row)) for row in rows]
    
    def hybrid_search(self,
                     table_name: str,
                     query_text: str,
                     query_embedding: List[float] = None,
                     top_k: int = 10,
                     filter_condition: str = None,
                     vector_weight: float = 0.7,
                     text_weight: float = 0.3,
                     metric: str = "COSINE") -> List[Dict]:
        """混合检索：向量检索 + 全文检索"""
        if query_embedding is None:
            query_embedding = self.embedding.encode_text(query_text)
        
        vector_results = self.vector_search(table_name, query_embedding, top_k * 2, filter_condition, metric)
        
        query_escaped = self.transform_string(query_text)
        text_search_sql = f"""
        SELECT id, content_type, content, title, metadata, create_time, _text_search_score AS text_score
        FROM {table_name}
        WHERE textSearch(content, '{query_escaped}')
        {f'AND {filter_condition}' if filter_condition else ''}
        ORDER BY text_score DESC
        LIMIT {top_k * 2}
        """
        text_rows = self._execute_sql(text_search_sql, query_type="select")
        text_results = [dict(zip(['id', 'content_type', 'content', 'title', 'metadata', 'create_time', 'text_score'], row)) 
                       for row in text_rows]
        
        # RRF 融合算法
        all_results = {}
        k = 60
        
        for rank, item in enumerate(vector_results):
            doc_id = item['id']
            if doc_id not in all_results:
                all_results[doc_id] = item
            all_results[doc_id]['vector_rank'] = rank
        
        for rank, item in enumerate(text_results):
            doc_id = item['id']
            if doc_id not in all_results:
                all_results[doc_id] = item
            all_results[doc_id]['text_rank'] = rank
        
        for doc_id, item in all_results.items():
            vector_score = 1.0 / (k + item.get('vector_rank', 10000))
            text_score = 1.0 / (k + item.get('text_rank', 10000))
            item['final_score'] = vector_weight * vector_score + text_weight * text_score
        
        sorted_results = sorted(all_results.values(), key=lambda x: x['final_score'], reverse=True)
        return sorted_results[:top_k]
    
    def text_search_image(self, table_name: str, query_text: str, top_k: int = 10, **kwargs) -> List[Dict]:
        """以文搜图"""
        filter_cond = "content_type = 'image'"
        if 'filter_condition' in kwargs:
            filter_cond += f" AND {kwargs.pop('filter_condition')}"
        
        instruction = kwargs.pop('instruction', None)
        query_embedding = self.embedding.encode_text(query_text, instruction)
        return self.vector_search(table_name, query_embedding, top_k, filter_condition=filter_cond, **kwargs)
    
    def image_search_image(self, table_name: str, image_url: str, top_k: int = 10, **kwargs) -> List[Dict]:
        """以图搜图"""
        filter_cond = "content_type = 'image'"
        if 'filter_condition' in kwargs:
            filter_cond += f" AND {kwargs.pop('filter_condition')}"
        
        instruction = kwargs.pop('instruction', None)
        query_embedding = self.embedding.encode_image(image_url, instruction)
        return self.vector_search(table_name, query_embedding, top_k, filter_condition=filter_cond, **kwargs)
    
    def text_search_video(self, table_name: str, query_text: str, top_k: int = 10, **kwargs) -> List[Dict]:
        """以文搜视频"""
        filter_cond = "content_type = 'video'"
        if 'filter_condition' in kwargs:
            filter_cond += f" AND {kwargs.pop('filter_condition')}"
        
        instruction = kwargs.pop('instruction', None)
        query_embedding = self.embedding.encode_text(query_text, instruction)
        return self.vector_search(table_name, query_embedding, top_k, filter_condition=filter_cond, **kwargs)
    
    def transform_string(self, s: str) -> str:
        # Remove all single quotes
        s = s.replace("'", "")
        # Split each character with |
        return "|".join(s)
