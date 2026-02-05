---
name: web-search
description: 使用内置 web_search 函数进行网页搜索并返回摘要结果, 准备清晰具体的 `query`。运行脚本 `python scripts/web_search.py "query"`。根据返回的摘要列表组织答案，不新增或臆造内容。
license: Complete terms in LICENSE.txt
---

# Web Search

## 适用场景

当需要从公开网页快速获取摘要信息时，使用该技能调用 `web_search` 函数。

## 使用步骤

1. 准备清晰具体的 `query`。
2. 运行脚本 `python scripts/web_search.py "query"`。运行之前cd到对应的目录。
3. 根据返回的摘要列表组织答案，不新增或臆造内容。

## 认证与凭据来源

- 优先读取 `VOLCENGINE_ACCESS_KEY` 与 `VOLCENGINE_SECRET_KEY` 环境变量。
- 若未配置，将尝试使用 VeFaaS IAM 临时凭据。

## 输出格式

- 按行输出摘要列表，最多 5 条。
- 若调用失败，将打印错误响应。

## 示例

```bash
python scripts/web_search.py "2026 年最新的 Python 版本"
```
