# byted-viking-aisearch-feishu

基于飞书开放平台的只读技能封装，用于搜索与读取：

- 云文档（doc/docx）
- 电子表格（sheet）
- 多维表格（bitable）
- 知识库（wiki 空间 / 节点）

## 快速开始

1. 配置访问凭证（推荐用户访问令牌）：

```bash
export LARK_USER_ACCESS_TOKEN="u-xxxxxxxxxxxxxxxxxxxxxxxx"
```

2. 代码调用示例：

```python
from scripts import FeishuDocSearch

tool = FeishuDocSearch()  # 或 FeishuDocSearch(access_token="u-xxx")

res = tool.search_items(search_key="项目", count=5, offset=0)
print(res)

# 读取首条结果原文/内容
items = res.get("data", {}).get("items", [])
if items:
    item = items[0]
    content = tool.fetch_raw_content(item["docs_type"], item["docs_token"])
    print(content)
```

## 权限与鉴权

- 通过 `Authorization: Bearer <LARK_USER_ACCESS_TOKEN>` 访问
- 读取多维表格（bitable）需要在 OAuth 用户授权里包含多维表格相关权限并重新授权

## 接口参考

- Feishu: `POST /open-apis/suite/docs-api/search/object`
- Docx: `GET /open-apis/docx/v1/documents/:document_id/raw_content`
- Doc: `GET /open-apis/docs/v2/documents/:document_id/raw_content`
- Sheets: `GET /open-apis/sheets/v2/spreadsheets/:spreadsheetToken/values_batch_get`
- Bitable: `GET /open-apis/bitable/v1/apps/:app_token/tables`
