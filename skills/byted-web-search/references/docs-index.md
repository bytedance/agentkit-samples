# Byted Web Search 文档索引

火山引擎联网搜索 API 文档，详见官网。

## 核心文档

| 文档 | 链接 |
|------|------|
| 联网搜索 API（主文档） | https://www.volcengine.com/docs/85508/1650263 |
| 新版 API 参考 | https://www.volcengine.com/docs/87772/2272953 |
| 产品简介 | https://www.volcengine.com/docs/87772/2272949 |
| 产品计费 | https://www.volcengine.com/docs/87772/2272951 |
| 新功能发布记录 | https://www.volcengine.com/docs/87772/2272950 |

## 控制台

| 用途 | 链接 |
|------|------|
| 新用户开通 | https://console.volcengine.com/search-infinity/web-search |
| API Key 管理 | https://console.volcengine.com/search-infinity/api-key |
| Coding Plan 控制台 | https://console.volcengine.com/ark/region:ark+cn-beijing/openManagement?LLM=%7B%7D&advancedActiveKey=subscribe&projectName=default |
| Coding Plan 企业版控制台 | https://console.volcengine.com/ark/region:ark+cn-beijing/openManagement?LLM=%7B%7D&advancedActiveKey=enterprise&projectName=default |

## 凭证说明

> ⚠️ 本 skill 仅支持联网搜索控制台或 Coding Plan 签发的 Key，其他来源 Key 不通用。

相关但凭证不通用的产品：[火山方舟联网搜索](https://www.volcengine.com/docs/82379/1756990)（Ark 工具）。

## 故障

| 错误码/信息 | 原因 | 解决方案 |
|------------|------|----------|
| `invalid_api_key` / `10403` | Key 无效、不匹配或无权限 | 确认 Key 来自 [联网搜索控制台](https://console.volcengine.com/search-infinity/api-key) 或 [Coding Plan控制台](https://console.volcengine.com/ark/region:ark+cn-beijing/openManagement?LLM=%7B%7D&advancedActiveKey=subscribe&projectName=default)。其他来源 Key 不通用。检查已开通、Key 无空格。Claw 中可重新在聊天框发正确的 Key |
| `401 InvalidAccessKey` | AK/SK 无效或失效 | 检查 AK/SK 是否正确或已过期，或改用 API Key 方式 |
| `429` / `FlowLimitExceeded` | 请求频率过高 | 降频后重试，单 Key 并发建议 ≤ 5 |
| `700429` | 免费链路限流 | 降频后重试 |
| `10400` | 参数错误 | 检查 Query、Count、TimeRange 等格式 |
| `10402` | 搜索类型非法 | 检查 `--type` 是否为 `web` 或 `image` |
| `10406` | 免费额度已耗尽 | 检查账户额度或联系支持 |
| `10407` | 当前无可用免费策略 | 检查账户状态或联系支持 |
| `10500` | 服务内部错误 | 等待 2-3 秒后重试一次 |
| `100013` | 子账号未授权 | 需授权 `TorchlightApiFullAccess` |
| `10408`/ `FunctionUnavailable`|欠费 | 后付费欠费 | 访问 https://console.volcengine.com/search-infinity/web-search 充值（24h 内可恢复） |
| `10409` | 套餐模式不支持当前搜索类型 | 更换匹配套餐的搜索模式 |
| `10412` | 搜索套餐额度不足 | 提示用户付费充值 |
| `未找到凭证` | 未设置任何认证方式 | 输出第 3 节首次回复模板引导用户配置 |
