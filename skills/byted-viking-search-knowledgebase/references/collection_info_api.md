---

本节将说明如何查看一个已创建知识库的信息。
<span id="818f2260"></span>
# 概述
/api/knowledge/collection/info 接口用于查看知识库详情，根据知识库名称返回知识库的描述，以及知识库配置的实验版本详细信息。
<span id="b2088fbc"></span>
# **前提条件**
完成“签名鉴权方式“页面的注册账号、实名认证、AK/SK 密钥获取和签名获取后，可调用 API 接口实现知识库信息查看的功能。
<span id="5ca54010"></span>
# **请求接口**

| | | | \
|**URI** |/api/knowledge/collection/info |统一资源标识符 |
|---|---|---|
| | | | \
|**请求方法** |POST |客户端对向量数据库服务器请求的操作类型 |
| | | | \
|**请求头** |Content-Type: application/json |请求消息类型 |
|^^| | | \
| |Authorization: HMAC-SHA256 *** |鉴权 |

<span id="4b10073f"></span>
# **请求参数（旗舰版、标准版通用）**

| | | | | | \
|**参数** |**类型** |**是否必选** |**默认值** |**参数说明** |
|---|---|---|---|---|
| | | | | | \
|name |string |否 |-- |**知识库名称** |
| | | | | | \
|project |string |否 |default |**知识库所属项目，获取方式参见文档**[API 接入与技术支持](/docs/84313/1606319#1ab381b9) |\
| | | | |:::warning |\
| | | | |若需要操作指定项目下的知识库，需正确配置该字段。 |\
| | | | |::: |
| | | | | | \
|resource_id |string |否 |-- |**知识库唯一 id** |\
| | | | |可选择直接传 resource_id ，或同时传 name 和 project 作为知识库的唯一标识 |

<span id="85fbb85b"></span>
# 
<span id="d47c3787"></span>
# **响应消息**

| | | \
|**参数** |**参数说明** |
|---|---|
| | | \
|code |状态码 |
| | | \
|message |返回信息 |
| | | \
|request_id |标识每个请求的唯一标识符 |
| | | \
|data |检索返回内容 |

data 返回值

| | | | | \
|字段 |子字段 |字段类型 |说明 |
|---|---|---|---|
| | | | | \
|collection_name |-- |string |知识库名称 |
| | | | | \
|version |-- |int |2：标准版 |\
| | | |4：旗舰版 |
| | | | | \
|description |-- |string |知识库描述 |
| | | | | \
|doc_num |-- |int |知识库内文档数 |
| | | | | \
|create_time |-- |int |知识库创建的时刻 |
| | | | | \
|update_time |-- |int |知识库更新的时刻 |
| | | | | \
|creator |-- |string |知识库创建用户 |
| | | | | \
|pipeline_list | |list |知识库下实验版本 (pipeline) 列表 |
|^^| | | | \
| |pipeline_stat |json |pipeline 下文档导入状态 |\
| | | | |\
| | | |```JSON |\
| | | |{ |\
| | | |    "doc_num": 1, // 导入文档数 |\
| | | |    "finish_doc_num": 1, // 完成导入文档数 |\
| | | |    "point_num": 1, // 切片数 |\
| | | |    "success_doc_num": 1 // 成功导入文档数（已完成解析切片） |\
| | | |}, |\
| | | |``` |\
| | | | |\
| | | | |
|^^| | | | \
| |index_list |list |知识库索引详情 |
|^^| | | | \
| |preprocessing_list |list |知识预处理配置 |\
| | | |```JSON |\
| | | |{ |\
| | | |    "chunking_strategy": "custom_balance",// 切片策略 |\
| | | |    "chunking_identifier": null, // 自定义分隔符 |\
| | | |    "chunk_length": 2000, // 切片最大长度 |\
| | | |    "merge_small_chunks": true // 是否合并短文本片 |\
| | | |    "vlm_prompt": "xxx", // 视频切片规则 |\
| | | |    ... |\
| | | | } |\
| | | |``` |\
| | | | |\
| | | |完整参数说明参考 [请求参数（旗舰版）](/docs/84313/1254593#6a604dca) |
|^^| | | | \
| |table_config_list |list |结构化知识库表结构 |\
| | | | |\
| | | |```JSON |\
| | | |{ |\
| | | |  "table_type": "row","col", |\
| | | |  // row表示从行开始解析，col表示从列开始解析, |\
| | | |  "table_pos": "int", |\
| | | |  // 字段位于第几行或第几列, |\
| | | |  "start_pos": "int", |\
| | | |  // 起始数据在第几行, |\
| | | |  "table_fields": [ |\
| | | |      {  |\
| | | |          "field_name": "xxx", //字段名称 |\
| | | |          "field_type": "int64", //字段类型, 支持string, int64, float32, bool，list<string> |\
| | | |          "if_embedding": true, //是否参与索引 |\
| | | |          "default_value":"xxx", //默认值 |\
| | | |          "if_filter": false //是否为标签过滤字段 |\
| | | |    }, |\
| | | |    ..... |\
| | | |  ] |\
| | | |} |\
| | | |``` |\
| | | | |\
| | | | |
|^^| | | | \
| |data_type |string |知识库内的数据类型 |
| | | | | \
|resource_id |-- |string |知识库唯一标识id |
| | | | | \
|project |-- |sring |知识库所属项目 |
| | | | | \
|type | |list |知识库类型信息 |

index_list 返回值

| | | | | \
|字段 |子字段 |字段类型 |说明 |
|---|---|---|---|
| | | | | \
|index_type |-- |string |索引算法 |
| | | | | \
|index_config | |list |索引配置详情 |
|^^| | | | \
| |vector_field |json |稠密向量字段 |\
| | | |```JSON |\
| | | |{ |\
| | | |    "field_name": "_sys_auto_content_vector", // 字段名 |\
| | | |    "field_type": "vector", // 字段类型 |\
| | | |    "dim": 2048 // 向量维度 |\
| | | |} |\
| | | |``` |\
| | | | |\
| | | | |
|^^| | | | \
| |sparse_vector_field | |稀疏向量字段 |\
| | | |```JSON |\
| | | |{ |\
| | | |    "field_name": "_sys_auto_content_vector", // 字段名 |\
| | | |    "field_type": "vector", // 字段类型 |\
| | | |} |\
| | | |``` |\
| | | | |\
| | | | |
|^^| | | | \
| |cpu_quota |int | CPU 配额 |
|^^| | | | \
| |distance |string |距离类型 |
|^^| | | | \
| |quant |string |量化方式 |
|^^| | | | \
| |embedding_model |string |向量化模型 |
|^^| | | | \
| |embedding_dimension |int |向量维度 |
|^^| | | | \
| |need_instruction |bool |是否拼接 instruction 进行检索 |
|^^| | | | \
| |fields |list[object] |数据集字段详情 |\
| | | |```JSON |\
| | | |[ |\
| | | |    { |\
| | | |    "field_name": "_sys_auto_id", // 字段名 |\
| | | |    "field_type": "string", // 字段类型 |\
| | | |    }, |\
| | | |    ...... |\
| | | |] |\
| | | |``` |\
| | | | |\
| | | | |
|^^| | | | \
| |field_enumerated_list |string |标签列表 |
| | | | | \
|primary_key |-- |sring |主键 |
| | | | | \
|status |-- |int |索引状态 |\
| | | |```Python |\
| | | |Status： |\
| | | |    -1:    待构建 |\
| | | |    0:     构建中 |\
| | | |    1:     构建完成 |\
| | | |    2:     构建失败 |\
| | | |    3:     变更中     |\
| | | |``` |\
| | | | |


<span id="af723eb1"></span>
## **状态码说明**

| | | | | \
|**状态码** |**http 状态码** |**返回信息** |**状态码说明** |
|---|---|---|---|
| | | | | \
|0 |200 |success |成功 |
| | | | | \
|1000001 |401 |unauthorized |鉴权失败 |
| | | | | \
|1000002 |403 |no permission |权限不足 |
| | | | | \
|1000003 |400 |invalid request：%s |非法参数 |
| | | | | \
|1000005 |400 |collection not exist |collection不存在 |

<span id="f61abe0e"></span>
# 完整示例
<span id="7f13d566"></span>
## 请求消息
```Shell
curl -i -X POST \
  -H 'Content-Type: application/json' \
  -H 'Authorization: HMAC-SHA256 ***' \
  https://api-knowledgebase.mlp.cn-beijing.volces.com
/api/knowledge/collection/info \
  -d '{
    "name": "test_collection_name",
    "project": ""
}'
```


<span id="416e041f"></span>
## 响应消息
执行成功返回：

```Shell
{
    "code": 0,
    "data": {
        "collection_name": "apiexample",
        "description": "test",
        "create_time": 1724747158,
        "update_time": 1724747158,
        "creator": "xxx",
        "pipeline_list": [
            {
                "pipeline_type": "user_define",
                "pipeline_stat": {
                    "doc_num": 0,
                    "finish_doc_num": 0,
                    "point_num": 0,
                    "success_doc_num": 0
                },
                "index_list": [
                    {
                        "index_type": "hnsw_hybrid",
                        "index_config": {
                            "vector_field": {
                                "field_name": "_sys_auto_content_vector",
                                "field_type": "vector",
                                "dim": 2048
                            },
                            "sparse_vector_field": {
                                "field_name": "_sys_auto_content_sparse_vector",
                                "field_type": "sparse_vector"
                            },
                            "cpu_quota": 1,
                            "distance": "ip",
                            "quant": "int8",
                            "embedding_model": "doubao-embedding-and-m3",
                            "embedding_dimension": 2048,
                            "need_instruction": true,
                            "fields": [
                                {
                                    "field_name": "_sys_auto_id",
                                    "field_type": "string"
                                },
                                {
                                    "field_name": "_sys_auto_doc_id",
                                    "field_type": "string"
                                },
                                {
                                    "field_name": "_sys_auto_chunk_id",
                                    "field_type": "int64"
                                },
                                {
                                    "field_name": "_sys_auto_doc_type",
                                    "field_type": "string"
                                },
                                {
                                    "field_name": "_sys_auto_add_type",
                                    "field_type": "string"
                                }
                            ]
                        },
                        "primary_key": "",
                        "status": -1
                    }
                ],
                "preprocessing_list": [
                    {
                        "chunking_strategy": "default",
                        "chunking_identifier": null,
                        "chunk_length": 2000
                    }
                ],
                "table_config_list": [
                    {
                        "table_type": "row",
                        "table_pos": 1,
                        "start_pos": 2,
                        "table_fields": [
                            {
                                "field_name": "讲解模块",
                                "field_type": "string",
                                "if_embedding": true,
                                "if_filter": false
                            },
                            {
                                "field_name": "子模块",
                                "field_type": "string",
                                "if_embedding": true,
                                "if_filter": false
                            },
                            {
                                "field_name": "问题示例",
                                "field_type": "string",
                                "if_embedding": true,
                                "if_filter": false
                            },
                            {
                                "field_name": "记忆化 ————讲解要点",
                                "field_type": "string",
                                "if_embedding": true,
                                "if_filter": false
                            }
                        ]
                    }
                ],
                "data_type": "structured_data"
            }
        ],
        "resource_id": "kb-be6833502748aaef",
        "project": "default"
    },
    "message": "success",
    "request_id": "02172474937697900000000000000000000ffff0a00501d3f1d67"
}
```


执行失败返回：
```Shell
HTTP/1.1 400 OK
Content-Length: 43
Content-Type: application/json
 
{"code":1000003, "message":"invalid request：%s", "request_id": "021695029757920fd001de6666600000000000000000002569b8f"}
```



