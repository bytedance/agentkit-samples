# Byted Web Search 文档索引

以下资料主要对应火山引擎融合信息搜索 API，是本 skill 依赖的底层文档。

所有文档均位于火山引擎官网。由于官网页面为动态渲染，部分内容无法静态抓取，建议直接在浏览器中访问。

## 核心文档

| 文档 | 链接 |
|------|------|
| **融合信息搜索API**（本skill对应的接口） | https://www.volcengine.com/docs/85508/1650263 |
| 火山如意数据结构 | https://www.volcengine.com/docs/85508/1995628 |
| 产品简介 | https://www.volcengine.com/docs/85508/1510774 |
| 产品计费 | https://www.volcengine.com/docs/85508/1510784 |
| 快速入门 | https://www.volcengine.com/docs/85508/1544858 |

## 操作指南

| 文档 | 链接 |
|------|------|
| 联网问答Agent操作指南 | https://www.volcengine.com/docs/85508/1512748 |
| 知识库操作指南 | https://www.volcengine.com/docs/85508/1666937 |
| 数据中心操作指南 | https://www.volcengine.com/docs/85508/1512697 |

## 鉴权与SDK

| 文档 | 链接 |
|------|------|
| Access Key管理 | https://www.volcengine.com/docs/6291/65568 |
| 签名方法 | https://www.volcengine.com/docs/6369/67269 |
| 官方签名示例（Python） | https://github.com/volcengine/volc-openapi-demos/blob/main/signature/python/sign.py |
| volcengine-python-sdk | https://github.com/volcengine/volcengine-python-sdk |
| veadk-python（Agent开发工具包） | https://pypi.org/project/veadk-python/ |

## 控制台入口

| 入口 | 链接 |
|------|------|
| 联网搜索API开通 | https://console.volcengine.com/ask-echo/web-search |
| 联网问答Agent控制台 | https://console.volcengine.com/ask-echo |

## API 关键参数速查

以下基于官方文档整理，详细说明见融合信息搜索API文档页面。当前脚本默认已支持 `web` / `image`、`count`、`time-range`、`auth-level`、`query-rewrite` 等常用参数；其中 `image` 搜索可通过 `--type image` 使用，且 `--count` 最多为 5。下表仍保留 API 原生字段，便于后续扩展。

### 请求

```
POST https://mercury.volcengineapi.com?Action=WebSearch&Version=2025-01-01
Content-Type: application/json
Authorization: HMAC-SHA256 Credential=..., SignedHeaders=..., Signature=...
```

ServiceName: `volc_torchlight_api`, Region: `cn-beijing`

### 请求体字段

| 字段 | 类型 | 必须 | 说明 |
|------|------|------|------|
| Query | String | 是 | 搜索关键词，1~100字符 |
| SearchType | String | 是 | `web` / `web_summary` / `image` |
| Count | Number | 否 | 返回条数（web最多50，image最多5） |
| NeedSummary | Boolean | 否 | 需要精准摘要（web_summary必须true） |
| TimeRange | String | 否 | `OneDay` / `OneWeek` / `OneMonth` / `OneYear` / `YYYY-MM-DD..YYYY-MM-DD` |
| Filter | Object | 否 | 当前脚本主要使用 `AuthInfoLevel` |
| Industry | String | 否 | finance / game |
| ContentFormats | String | 否 | Text / Markdown |
| QueryControl.QueryRewrite | Boolean | 否 | 开启 Query 改写；当前脚本已通过 `--query-rewrite` 暴露 |

### 响应体关键字段

| 字段 | 说明 |
|------|------|
| Result.ResultCount | 结果数量 |
| Result.WebResults[] | 网页搜索结果数组 |
| Result.ImageResults[] | 图片搜索结果数组 |
| Result.Choices[] | LLM总结内容（web_summary流式） |
| Result.Usage | Token消耗（web_summary尾帧） |
| Result.TimeCost | 耗时（毫秒） |
| ResponseMetadata.Error | 错误信息（如有） |

### WebResults 单项字段

Title, SiteName, Url, Snippet, Summary, Content, PublishTime, RankScore, AuthInfoDes, AuthInfoLevel

### ImageResults 单项字段

Title, SiteName, Url, PublishTime, Image.Url, Image.Width, Image.Height, Image.Shape

### 错误码

| 码 | 说明 |
|----|------|
| 10400 | 参数错误 |
| 10402 | 非法搜索类型 |
| 10403 | 权限错误 |
| 10500 | 内部错误（可重试） |
| 100013 | AccessDenied（子账号未授权） |
