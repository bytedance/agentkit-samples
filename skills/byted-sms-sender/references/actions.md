# Action 公共契约

本文只定义所有短信 Action 共享的调用规则。按任务继续读取：

- 资质、签名和模板申请：[application-contracts.md](application-contracts.md)
- 模板匹配、发送、群发和分析：[delivery-contracts.md](delivery-contracts.md)

## 调用配置

- CLI 已支持的 Action 使用 `ve volcsms <Action>`，最低版本 `1.1.0`
- 版本：`2026-01-01`
- endpoint：`https://sms.volcengineapi.com`（AK/SK 兼容直连）
- service：`volcSMS`
- region：`cn-north-1`
- 响应：`ResponseMetadata` 与 `Result`

当前 CLI 元数据尚未包含账号主体、资质要求、材料上传凭证、OCR、三要素校验和资质创建 Action；
这些 Action 由内置客户端复用同一份浏览器登录或 AK/SK 凭证直接调用。不得先调用 CLI
再根据写请求错误猜测是否切换路径。

POST Action 使用 `--body <JSON>`；GET Action 使用参数旗标。Profile 只通过
`VOLCENGINE_PROFILE` 或 `---profile` 选择，凭证不得进入命令行。每个 Action 总限流
50 QPS、单账号默认 5 QPS；查询必须有界，写操作不得因限流切换路径重放。

## Action 矩阵

| 能力 | Action | 方法 | 类型 | 对账 |
| --- | --- | --- | --- | --- |
| 消息组列表 | `ListSubAccountForAgent` | POST | read | 同一 Action |
| 消息组详情 | `GetSubAccountDetail` | GET | read | 同一 Action |
| 资质列表 | `GetSignatureIdentificationList` | POST | read | 同一 Action |
| 账号主体 | `ListAllSmsProduct` | GET | read | 同一 Action |
| 资质材料要求 | `GetAccountIdentRankForAgent` | GET | read | 同一 Action |
| ImageX 上传凭证 | `GetMUploadParam` | GET | read | 同一 Action |
| 证件 OCR | `GetOCRLicenseForAgent` | POST | read | 同一 Action |
| 企业校验 | `ThreeElementEnterpriseCheckForAgent` | POST | read | 同一 Action |
| 联系人校验 | `ThreeElementPersonCheckForAgent` | POST | read | 同一 Action |
| 创建资质 | `ApplySignatureIdentificationForAgent` | POST | mutation | 资质列表 |
| 发送短信验证码 | `SendSmsVerifyCodeByMobile` | POST | mutation | 无 |
| 校验短信验证码 | `CheckSmsVerifyCodeByMobile` | POST | mutation | 无 |
| 签名列表 | `ListSignatureForAgent` | POST | read | 同一 Action |
| 模板列表 | `ListSmsTemplateForAgent` | POST | read | 同一 Action |
| 二级模板详情 | `ListSecondTemplate` | GET | read | 同一 Action |
| 申请签名 | `ApplySmsSignatureV2` | POST | mutation | 签名列表 |
| 申请模板 | `ApplySmsTemplateV2` | POST | mutation | 模板列表 |
| 单条发送 | `SendSmsForAgent` | POST | mutation | 发送日志 |
| 发送日志 | `ListSmsSendLogForAgent` | POST | read | 同一 Action |
| 聚合统计 | `ListTotalSendCountStatForAgent` | POST | read | 同一 Action |
| 群发上传 URL | `GetUploadTosURL` | GET | mutation | 无 |
| 群发 CSV 示例 | `TemplateUploadDemo` | POST | read | 同一 Action |
| 创建群发任务 | `SetBatchTask` | POST | mutation | 任务详情 |
| 群发任务详情 | `GetBatchTaskDetail` | GET | read | 同一 Action |
| 群发任务列表 | `GetBatchTaskList` | GET | read | 同一 Action |
| 启动群发任务 | `ConsentBatchTask` | POST | mutation | 任务详情 |
| 取消群发任务 | `DeleteBatchTask` | POST | mutation | 任务详情 |

## 错误与重试

- HTTP 200 中存在 `ResponseMetadata.Error` 仍是失败。
- 查询操作仅对连接失败、HTTP 429、可重试 5xx 和公开业务码 `1015`、`1999`
  共用最多两次的有界退避预算。
- 写操作只发送一次；结果不确定时返回 `outcome_unknown` 并按矩阵对账。
- 短信验证码发送和校验使用公开业务码 `1017` 表示触发频率限制。
- 参数、权限、审核拒绝、冲突和公开 4xx 不重试。
- 除 `ListSmsSendLogForAgent` 外，Action 公共错误码为 `1001`、`1015`、`1023`、
  `1024`、`1999`、`RE:0000`、`RE:0001`、`SY:0500`。发送日志使用 `1001`、
  `1999`、`RE:0000`、`RE:0001`、`SY:0500`。

错误含义运行时查询官方文档，不在 Skill 中猜测：

- [发送接口错误码](https://www.volcengine.com/docs/6361/173288?lang=zh)
- [发送状态错误码](https://www.volcengine.com/docs/6361/173291?lang=zh)

`RE:0001` 仅用于路由服务开通流程。公开文档没有精确错误码时，保留错误码与
Request ID，并让客户携带这些客户可见信息联系支持。
