---
name: byted-viking-aisearch-feishu
description: |
  基于飞书开放平台 API 的云文档/电子表格/多维表格/知识库（Wiki）搜索与内容读取工具（只读）。
  使用场景：在飞书中搜索文档/表格/多维表格/知识库空间或节点，并读取对应内容。
  Also activates for: 飞书搜索、Feishu search docs sheets base wiki、Lark docs sheets base wiki search、搜索飞书文档 表格 多维表格 知识库
metadata:
  version: "1.0.0"
  openclaw:
    identity:
    - type: oauth
      provider: viking_feishu_oauth_provider
      env:
      - LARK_USER_ACCESS_TOKEN
      required: true
---

# Viking AISearch Feishu Skill

你是一个专注于飞书「云文档 / 电子表格 / 多维表格 / 知识库（Wiki）」的搜索与内容读取助手。你必须严格只读，不实现任何写操作。

## 🎯 核心功能

- 搜索：聚合搜索云文档（doc/docx）、电子表格（sheet）、多维表格（bitable）、知识库空间与节点（wiki）
- 读取：读取 doc/docx 原文；读取 sheet 预览区间数据；读取 bitable 表结构与记录样本；读取 wiki 节点（自动跳转到关联对象内容）与 wiki 空间子节点列表

## 🚦 场景路由

| 用户意图示例 | 匹配场景 | 主要方法 | 产出 |
| :-- | :-- | :-- | :-- |
| “搜一下飞书里关于‘Q4’的资料” | 聚合搜索 | `search_items()` / `search_docs()` | 返回条目列表（title/type/token/url/source…） |
| “读取这个 docx / sheet / base 的内容” | 内容读取 | `fetch_raw_content()` | 返回 `content`（纯文本/TSV/JSON 摘要） |
| “列出我有权限的知识库空间” | 知识库空间 | `list_wiki_spaces()` / `search_wiki_spaces()` | 返回空间列表 |
| “列出某个知识库空间的子节点” | 空间子节点 | `list_wiki_space_nodes()` | 返回节点列表 |

## 📚 主要接口使用方法

### 1) 初始化

```python
from scripts.feishu_search import FeishuDocSearch

# 方式一：使用环境变量（推荐）
# export LARK_USER_ACCESS_TOKEN="u-xxxxxxxxxxxxxxxxxxxxxxxx"
tool = FeishuDocSearch()

# 方式二：显式传入 access_token
tool = FeishuDocSearch(access_token="u-xxx")
```

### 2) 聚合搜索 - `search_items()`

**功能**：按关键词搜索云文档/电子表格/多维表格，并可选聚合知识库节点与知识库空间

**参数**：

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
| :-- | :-- | :-- | :-- | :-- |
| `search_key` | `str` | 是 | - | 搜索关键词 |
| `count` | `int` | 否 | `10` | 返回数量（分页后） |
| `offset` | `int` | 否 | `0` | 偏移量（分页后） |
| `types` | `List[str]` | 否 | `["doc","docx","sheet","bitable","wiki","wiki_space"]` | 搜索类型集合 |
| `owner_ids` | `List[str]` | 否 | `None` | 所有者 Open ID 过滤（仅 suite docs 搜索） |
| `chat_ids` | `List[str]` | 否 | `None` | 群聊 ID 过滤（仅 suite docs 搜索） |
| `space_id` | `str` | 否 | `None` | 仅搜索该知识库空间内节点（wiki 节点搜索） |

**返回语义**：

- 只要至少一条搜索路径返回可用结果，`search_items()` 仍可返回 `success=true`
- 若某一路径失败或降级，结果会在 `data.warnings` 中显式暴露，不再静默吞掉
- 常见 warning 键包括：`suite_error`、`suite_fallback_error`、`wiki_nodes_error`、`wiki_spaces_error`、`wiki_spaces_warning`

**典型部分成功返回**：

```json
{
  "success": true,
  "message": "搜索成功",
  "data": {
    "total": 3,
    "has_more": false,
    "items": [],
    "warnings": {
      "suite_error": {
        "message": "文档套件搜索失败",
        "error": {}
      }
    }
  }
}
```

### 3) 兼容接口 - `search_docs()`

`search_docs()` 为历史兼容接口，内部基于 `search_items()` 实现，默认包含 `doc/docx/sheet/bitable/wiki`。

**使用示例**：

```python
# 基础搜索
result = tool.search_docs(search_key="项目计划")

# 指定类型搜索
result = tool.search_docs(
    search_key="季度报告",
    docs_types=["doc", "docx", "sheet", "bitable", "wiki"]
)

# 分页搜索
result = tool.search_docs(
    search_key="技术方案",
    count=20,
    offset=0
)
```

**返回示例**：

```json
{
  "success": true,
  "message": "搜索成功",
  "data": {
    "total": 12,
    "has_more": false,
    "warnings": {
      "wiki_error": {
        "message": "权限不足，请为应用开通 wiki 搜索相关权限",
        "error": {
          "type": "permission_denied",
          "detail": "HTTP 403: ..."
        }
      }
    },
    "items": [
      {
        "docs_token": "your_docs_token_xxx",
        "docs_type": "docx",
        "owner_id": "ou_xxx",
        "title": "项目计划.docx",
        "url": "https://xxx.feishu.com/docx/xxx",
        "source": "suite_docs"
      },
      {
        "docs_token": "your_docs_token_xxx",
        "docs_type": "wiki",
        "title": "用户操作手册",
        "url": "https://xxx.feishu.com/wiki/xxx",
        "space_id": "your_space_id_xxx",
        "obj_type": "docx",
        "obj_token": "your_obj_token_xxx",
        "source": "wiki_nodes"
      }
    ]
  }
}
```

### 3.5) 搜索 wiki 节点 - `search_wiki_nodes()`

**功能**：按 wiki 节点标题/内容搜索知识库文档

**参数**：

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| `keyword` | `str` | 是 | - | 搜索关键词 |
| `count` | `int` | 否 | `None` | 返回数量 |
| `offset` | `int` | 否 | `None` | 偏移量 |
| `space_id` | `str` | 否 | `None` | 指定 wiki 知识空间 |

**使用示例**：

```python
result = tool.search_wiki_nodes(
    keyword="用户操作手册",
    space_id="your_space_id_xxx"
)
```

**返回示例**：

```json
{
  "success": true,
  "message": "搜索成功",
  "data": {
    "total": 1,
    "has_more": false,
    "items": [
      {
        "docs_token": "your_docs_token_xxx",
        "docs_type": "wiki",
        "title": "用户操作手册",
        "url": "https://xxx.feishu.com/wiki/xxx",
        "space_id": "your_space_id_xxx",
        "obj_type": "docx",
        "obj_token": "your_obj_token_xxx",
        "source": "wiki_nodes"
      }
    ]
  }
}
```

### 4) 内容读取 - `fetch_raw_content()`

支持的 `docs_type`：

- `doc` / `docx`：读取原文（raw_content）
- `sheet`：读取表格预览区间数据（默认首个工作表 `A1:Z100`，可传 `range_a1/max_rows/max_cols`）
- `bitable`：读取多维表格的数据表列表，并读取一个数据表的记录样本（可传 `table_id/page_size/page_token`）
- `wiki`：读取知识库节点；若节点关联对象为 doc/docx/sheet/bitable，会自动读取关联对象内容
- `wiki_space`：读取知识库空间的子节点列表（可分页）

**补充说明**：

- `search_wiki_spaces()` 命中分页上限时，会返回 `data.has_more=true`，并在 `data.warnings.pagination_truncated` 中说明结果可能不完整
- `fetch_sheet_content()` 在 metainfo 端点失败但 query 端点成功时，仍返回 `success=true`，并在 `data.warnings.metainfo_error` 中保留降级信息
- `fetch_bitable_content()` 在“表列表获取成功但记录样本读取失败”时，返回 `success=true` 和 `message=部分成功：已获取数据表列表，但记录样本读取失败`，同时在 `data.warnings.records_error` 中暴露失败详情

**使用示例**：

```python
# 读取 docx
result = tool.fetch_raw_content(
    docs_type="docx",
    docs_token="your_docs_token_xxx"
)

# 读取 sheet（可指定范围）
sheet_result = tool.fetch_raw_content(
    docs_type="sheet",
    docs_token="your_sheet_token_xxx",
    range_a1="Sheet1!A1:D50"
)

# 读取 bitable（可指定表与分页）
base_result = tool.fetch_raw_content(
    docs_type="bitable",
    docs_token="your_app_token_xxx",
    table_id="tbl_xxx",
    page_size=50
)
```

**返回示例（docx）**：

```json
{
  "success": true,
  "message": "获取成功",
  "data": {
    "content": "Q4项目计划\n一、项目背景..."
  }
}
```

## 🔑 鉴权

- 使用 `Authorization: Bearer <LARK_USER_ACCESS_TOKEN>`（用户访问令牌）
- 访问令牌通过 `viking_feishu_oauth_provider` 注入到环境变量 `LARK_USER_ACCESS_TOKEN`，实现动态获取

## 📝 使用流程建议

典型流程：搜索并读取内容

```python
# 1. 搜索
search_result = tool.search_docs(search_key="项目计划")
if not search_result.get("success"):
    print(search_result.get("message"))
    raise SystemExit

items = search_result.get("data", {}).get("items", [])
if not items:
    print("未找到相关文档")
    raise SystemExit

# 2. 获取第一个文档的 token 和类型
first_item = items[0]
docs_token = first_item["docs_token"]
docs_type = first_item["docs_type"]

# 3. 读取内容
content_result = tool.fetch_raw_content(docs_type=docs_type, docs_token=docs_token)
print(content_result)
```

## 📋 文档类型枚举

| docs_type  | 说明 |
| :--------- | :--- |
| `doc`      | 旧版飞书文档 |
| `docx`     | 新版飞书文档 |
| `sheet`    | 电子表格 |
| `bitable`  | 多维表格 |
| `wiki`     | 飞书 wiki 节点（可自动读取关联对象内容） |
| `wiki_space` | 知识库空间（可读取子节点列表） |

### 获取 wiki 节点信息 - `get_wiki_node()`

**功能**：获取 wiki 节点的详细信息，包括标题、关联对象类型等

**使用示例**：

```python
result = tool.get_wiki_node(node_token="your_node_token_xxx")
```

**返回示例**：

```json
{
  "success": true,
  "message": "获取成功",
  "data": {
    "node_token": "your_node_token_xxx",
    "title": "文档标题",
    "obj_type": "docx",
    "obj_token": "your_obj_token_xxx",
    "node_type": "origin",
    "space_id": "your_space_id_xxx",
    "creator": "ou_xxx",
    "owner": "ou_xxx"
  }
}
```

## 🚨 错误处理

| 错误类型     | 识别方式                 | 返回提示                              |
| :------- | :------------------- | :-------------------------------- |
| 认证失败     | `401`/`Unauthorized` | "认证失败，请检查 access_token 是否有效或已过期" |
| 权限不足     | `403`/`Forbidden`    | "权限不足，请为应用开通搜索相关权限"            |
| 请求超时     | 包含 `timeout`         | "请求超时，请稍后重试"                      |
| 搜索参数错误   | `search_key` 为空      | "search_key 不能为空"                |
| 不支持的文档类型 | 未知的 `docs_type`      | "不支持的 docs_type，仅支持 doc/docx/sheet/bitable/wiki/wiki_space"  |
