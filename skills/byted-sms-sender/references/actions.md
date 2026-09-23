# Action 公共契约

## 调用约定

全部 Action 使用 `2026-01-01`。Profile 用 `VOLCENGINE_PROFILE` 或 `--profile`，凭据由客户端读取。
查询传接口原生参数，例如：

```json
{"action":"ListSignatureForAgent","params":{"Page":1,"PageSize":100}}
```

CLI 等价调用为 `api-read --action ListSignatureForAgent --params '{"Page":1,"PageSize":100}'`。
参数保留原生名称与类型。消息组 ID 取 `GetSubAccountListForAgent` 返回的 `subAccountId`，名称用于展示。
List/list 为当前页，Total/total 为筛选总数，按实际查询范围说明结论。
资质校验、上传等接口由私密表单调用。

## Action 矩阵

| 能力 | Action | 方法 | 类型 | 后续查询 |
| --- | --- | --- | --- | --- |
| 消息组列表 | `GetSubAccountListForAgent` | POST | read | 同一 Action |
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
| 签名汇总列表 | `ListSignatureForAgent` | POST | read | 同一 Action |
| 签名列表（支持项目、消息组、短信类型、行业、状态筛选） | `ListSignaturesForAgent` | POST | read | 同一 Action |
| 普通模板列表 | `ListSmsTemplateForAgent` | POST | read | 同一 Action |
| 群发模板目录 | `ListBatchTemplatesForAgent` | POST | read | 同一 Action |
| 二级模板列表 | `ListSecondTemplate` | GET | read | 同一 Action |
| 申请签名 | `ApplySmsSignatureV2` | POST | mutation | 签名列表 |
| 申请模板 | `ApplySmsTemplateV2` | POST | mutation | 模板列表 |
| 单条发送 | `SendSmsForAgent` | POST | mutation | 发送日志 |
| 发送日志 | `ListSmsSendLogForAgent` | POST | read | 同一 Action |
| 聚合统计 | `GetTotalSendCountStatV4ForAgent` | POST | read | 同一 Action |
| 群发上传 URL | `GetUploadTosURL` | GET | mutation | 无 |
| 群发正文预检 | `ValidateBatchTaskContentForAgent` | POST | read | 同一 Action |
| 群发 CSV 示例 | `TemplateUploadDemoForAgent` | POST | read | 同一 Action |
| 创建群发任务 | `SetBatchTaskForAgent` | POST | mutation | 任务详情 |
| 群发任务详情 | `GetBatchTaskDetail` | GET | read | 同一 Action |
| 群发任务列表 | `GetBatchTaskList` | GET | read | 同一 Action |
| 启动群发任务 | `ConsentBatchTask` | POST | mutation | 任务详情 |
| 取消群发任务 | `DeleteBatchTask` | POST | mutation | 任务详情 |

## 错误与重试

- `ResponseMetadata.Error` 提供业务错误，HTTP 状态与业务状态分别读取。
- 查询操作仅对连接失败、HTTP 429、可重试 5xx 和公开业务码 `1015`、`1999`
  共用最多两次的有界退避预算。
- `tls_certificate_error`：由宿主修复可信证书配置后恢复查询。
- 写操作只发送一次；结果不确定时保留 `outcome_unknown` 和 Request ID，由 Agent 选择后续查询核实。
- 短信验证码发送和校验使用公开业务码 `1017` 表示触发频率限制。
- 参数、权限、审核拒绝、冲突和公开 4xx 保留错误，处理其原因后再准备后续操作。
- 除 `ListSmsSendLogForAgent` 外，Action 公共错误码为 `1001`、`1015`、`1023`、
  `1024`、`1999`、`RE:0000`、`RE:0001`、`SY:0500`。发送日志使用 `1001`、
  `1999`、`RE:0000`、`RE:0001`、`SY:0500`。

错误含义按需查阅官方文档：

- [发送接口错误码](https://www.volcengine.com/docs/6361/173288?lang=zh)
- [发送状态错误码](https://www.volcengine.com/docs/6361/173291?lang=zh)

`RE:0001` 仅用于路由服务开通流程。公开文档没有精确错误码时，保留错误码与
Request ID，并让客户携带这些客户可见信息联系支持。

## 查询结果

保留全部业务字段、嵌套结构、审核维度和业务长文本，由 Agent 按客户问题展示。
凭据、证件和个人私密字段由脚本处理；手机号掩码展示，携带凭据的 URL 脱敏展示。
