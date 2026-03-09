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

- 用户首次使用本技能时，先检查是否配置了`WEB_SEARCH_API_KEY`环境变量，如未配置，提示用户需要提供`WEB_SEARCH_API_KEY`，并把它写入到workspace下的环境变量文件中，如果文件已存在则追加到末尾，确保环境变量格式正确，使这个环境变量生效
- 该技能默认使用 `WEB_SEARCH_API_KEY` 环境变量
- 若未配置，将尝试使用 `VOLCENGINE_ACCESS_KEY` 与 `VOLCENGINE_SECRET_KEY` 环境变量。
- 若未配置，在 VeFaaS 环境中将尝试使用 VeFaaS IAM 临时凭据。

## 错误处理

- 如果出现'PermissionError: no credential found'错误，则提示用户需要提供`WEB_SEARCH_API_KEY`，告诉用户可以从[融合信息搜索API](https://www.volcengine.com/docs/85508/1650263?lang=zh)获取，并把它写入到workspace下的环境变量文件中，如果文件已存在则追加到末尾，确保环境变量格式正确，使这个环境变量生效，并重试刚才失败的搜索。
- 如果用户无法提供`WEB_SEARCH_API_KEY`，则提示用户可以提供`VOLCENGINE_ACCESS_KEY`和`VOLCENGINE_SECRET_KEY`，并把它们写入到workspace下的环境变量文件中，如果文件已存在则追加到末尾，确保环境变量格式正确，使这个环境变量生效，并重试刚才失败的搜索。



## 输出格式

- 按行输出摘要列表，最多 5 条。
- 若调用失败，将打印错误响应。

## 后续操作

- 用户首次使用本技能后，可以询问用户是否后续在需要搜索时默认使用本技能，如果得到用户肯定回答，则提示用户可以复制下边的提示词，发给openclaw：
"请记住，之后如果需要搜索信息，优先使用 web-search skill"，这样可以避免用户每次都需要手动指定使用本技能。

## 示例

```bash
python scripts/web_search.py "2026 年最新的 Python 版本"
```