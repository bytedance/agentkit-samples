# 对外 Action 契约

本文档是本 Skill 完整的人类可读契约。运行时代码只保留调用 Action 所需的最小
调用元数据，契约测试必须保证两者一致。

调用身份由本次选中的鉴权路径确定。优先通过官方 CLI 的
`ve volcsms <Action>` 执行；CLI 不可用且确认请求尚未发出时，兼容直连模式使用
火山引擎 V4 AK/SK。所有 Action 的公共配置为：

- CLI service：`volcsms`
- CLI 最低版本：`1.1.0`
- endpoint：`https://sms.volcengineapi.com`（兼容直连模式）
- service：`volcSMS`
- region：`cn-north-1`
- path：`/`
- 响应信封：`ResponseMetadata` 与 `Result`

所有 Action 使用已发布的 `2026-01-01` 版本。签名、模板、资质、上传及群发
Action 按要求复用现有控制台/OpenAPI Handler。执行任何线上写操作前，必须使用
专用客户测试身份验证可达性。公开 API 不可达属于上游契约阻塞，不得绕过公开接口
或调用未发布能力。

POST Action 通过 `ve volcsms <Action> --body <JSON>` 调用，GET Action 使用
对应 `--<参数名> <值>` 旗标。Profile 只通过 `VOLCENGINE_PROFILE` 或 CLI
`---profile` 选择；AK/SK 和 Session Token 绝不能出现在命令行参数中。Python
入口继续统一执行字段白名单、脱敏、预检与写操作授权门禁。

每个 Action 的 API 总限流为 50 QPS，单客户默认限制为 5 QPS。查询流程必须限制
分页数量，并仅对公开瞬时错误执行有界退避。限流额度绝不代表可以自动重试写操作。

## Action 矩阵

| 能力 | Action | 版本 | 方法 | 类型 | 对账方式 |
| --- | --- | --- | --- | --- | --- |
| 查询消息组 | `ListSubAccountForAgent` | `2026-01-01` | POST | read | 同一 Action |
| 查询消息组详情 | `GetSubAccountDetail` | `2026-01-01` | GET | read | 同一 Action |
| 查询资质 | `GetSignatureIdentificationList` | `2026-01-01` | POST | read | 同一 Action |
| 查询签名 | `ListSignatureForAgent` | `2026-01-01` | POST | read | 同一 Action |
| 查询模板 | `ListSmsTemplateForAgent` | `2026-01-01` | POST | read | 同一 Action |
| 查询二级模板 | `ListSecondTemplate` | `2026-01-01` | GET | read | 同一 Action |
| 申请签名 | `ApplySmsSignatureV2` | `2026-01-01` | POST | mutation | 查询签名 |
| 申请模板 | `ApplySmsTemplateV2` | `2026-01-01` | POST | mutation | 查询模板 |
| 发送短信 | `SendSmsForAgent` | `2026-01-01` | POST | mutation | 发送日志 |
| 查询发送日志 | `ListSmsSendLogForAgent` | `2026-01-01` | POST | read | 同一 Action |
| 查询聚合统计 | `ListTotalSendCountStatForAgent` | `2026-01-01` | POST | read | 同一 Action |
| 获取上传 URL | `GetUploadTosURL` | `2026-01-01` | GET | mutation | 无 |
| 获取群发 CSV 示例 | `TemplateUploadDemo` | `2026-01-01` | POST | read | 同一 Action |
| 创建群发任务 | `SetBatchTask` | `2026-01-01` | POST | mutation | 任务详情 |
| 查询任务详情 | `GetBatchTaskDetail` | `2026-01-01` | GET | read | 同一 Action |
| 查询任务列表 | `GetBatchTaskList` | `2026-01-01` | GET | read | 同一 Action |
| 启动任务 | `ConsentBatchTask` | `2026-01-01` | POST | mutation | 任务详情 |
| 取消任务 | `DeleteBatchTask` | `2026-01-01` | POST | mutation | 任务详情 |

以上写 Action 均没有已确认的服务端幂等字段。每个写操作最多发送一次；请求发送后
响应丢失时，状态保持 `outcome_unknown`，直到对账成功。CLI 写调用超时、返回
非结构化结果或无法判断是否已经发出请求时，不得切换兼容路径重放。

## 查询契约

### ListSubAccountForAgent

可选 Body 字段：`SubAccountName`。结果包含已审核消息组。不得发送 `Account`
字段，身份来自当前鉴权路径。

### GetSubAccountDetail

必填 GET 字段：`subAccount`。不得发送 `Account`。

只返回 `subAccountId`、`subAccountName`、`status` 和
`channelTypeToIndustryConfig`。映射项只允许包含 `channelType`、
`channelTypeCn`、`industry`、`industryCn`。该 Action 用于解释消息组的
短信类型和计费行业，不是签名申请门禁。普通客户通常使用通用行业，申请签名时
无需选择行业。

### GetSignatureIdentificationList

必填 Body 字段：整数 `pageIndex`、`pageSize`。可选字段为整数 `id`、字符串
`materialName` 和可重复传入的整数 `status`。已发布 Action 中，`ids` 和
`isOrder` 不是请求字段；`isOrder` 仅存在于响应。

只返回以下客户安全字段：

- 资质 `id`
- `purpose`
- `materialName`
- `businessCertificateName`
- `effectSignatures`
- `auditStatus`、`auditOpinion`、`auditedAt`
- `usable`、`isOrder`

不得返回身份证号、个人手机号、材料文件 URL、操作人信息或原始业务材料。

签名申请只能选择 `usable=true` 且审核已完成/通过的资质。不得暴露
`ApplySignatureIdentification`。

### ListSignatureForAgent

Body 字段：

- 可选 `Signature`
- 可选 `SubAccounts` 数组
- `Page` 与 `PageSize`

匹配前移除外围 `【】`、`[]` 或 `［］`。

国内资源校验中，状态 `3` 表示审核通过，`5` 表示免审，`2` 表示拒绝。
签名申请要求另行选择已审核资质。模板申请要求签名已审核，且与目标消息组及短信
类型关系有效；允许省略冗余 `usable`，但明确 `usable=false` 必须拒绝。
群发预检也允许已按目标消息组限定的已审核签名记录缺少 `usable` 或资质 ID；
返回资质 ID 时必须重新查询该公开资质。单条发送预检更精简：签名状态为
`3`/`5` 且绑定目标消息组时，可以缺少 `usable`、
`IdentificationId`/`IdentificationID` 或 `ChannelTypes`；明确
`usable=false` 必须拒绝。

### ListSmsTemplateForAgent

Body 字段：

- 可选 `TemplateId`
- 可选 `SubAccounts` 数组
- 可选 `Signatures` 数组
- `Page` 与 `PageSize`

公开模板摘要包含单数 `Signature: string` 和整数 Unix 秒
`CreatedAt`，也可能包含兼容关系 `Signatures: string[]`。将
`Signature`/`signature` 与 `Signatures`/`signatures` 规范为同一关系：
缺失表示按签名限定的查询没有重复返回该关系；明确空值表示不匹配；同时返回但互不
相交时返回 `contract_conflict`。只在服务端实际返回时使用模板变量、短信类型、
消息组、状态、名称和内容。公开 CLI 列表输出使用 UTF-8 字节长度与 SHA-256
替换模板内容。

单条发送与模板匹配时，按已知模板 ID、签名和消息组限定查询。可用候选必须状态为
`3` 或 `5`，且返回的签名、消息组关系与本次发送一致；仅存在名称相似模板不够。
两个模板查询本身都可按签名限定，因此 `ListSecondTemplate` 省略签名关系时可以
接受。已发布结构使用 `signatures: string[]`，而 `2026-01-01` 的成功响应也
曾返回单数 `signature: string`；必须同时兼容，只要任一结构存在就要求与目标
签名一致。

### ListSecondTemplate

GET 字段包括 `project`、`templateId`、`secondTemplateId` 和
`signatures`。当 Agent 模板响应缺少所需名称、内容、变量列表或消息组关系时，
使用该 Action 获取 V2 模板详情。模板精确匹配与单条发送预检必须使用解析后的详情
校验内容完全一致，以及模板变量名集合完全一致。实际成功响应还确认
`createdAt`/`updatedAt` 为整数 Unix 时间戳。

### ListSmsSendLogForAgent

Body 字段：

- 必填 `SubAccount`、`Page`、`PageSize`
- 可选 `FromTime`、`ToTime`、`Mobile`、`TemplateId`、`Signature`、
  `MessageId`

`Mobile` 仅用于请求过滤，响应中即使脱敏也不得返回。跨页聚合时使用
`MessageId` 作为稳定去重键。分析输出只允许消息 ID、发送/回执时间、公开错误码、
短信条数、消息组、签名和模板 ID。即使服务端返回，也要丢弃手机号、内容、变量、
账号及其他非客户可见字段。

请求字段 `FromTime`、`ToTime` 使用 Unix 秒时间戳。分析窗口按 `[start, end)`
表示时，请求的 `ToTime` 传入结束时刻前 1 秒。响应字段 `SendTime`、
`ReceiptTime` 使用 Unix 毫秒时间戳；解析和按时间分组时不得将其误当成秒。

统计回执状态时：非空公开错误码且不属于文档定义的成功标记，计为失败；存在回执
时间且没有这类错误码，计为成功；两者都没有则计为未回执。这是面向客户的记录
分类，不是对非公开实现原因的推断。

### ListTotalSendCountStatForAgent

Body 字段：

- 必填 `StartTime`、`EndTime`
- 可选 `SubAccount`、`ChannelType`、`Signature`、`TemplateId`

公开结果字段为 `TotalSendCount`、`TotalAllSendCount`、
`TotalSendSuccessCount`、`TotalReceiptSuccessCount`、
`TotalReceiptFailureCount`。提交成功率按
`TotalSendSuccessCount / TotalAllSendCount` 计算，回执成功率按
`TotalReceiptSuccessCount / TotalSendSuccessCount` 计算。必须根据计数
字段重新计算并展示字段名、分子、分母和百分比，不要静默信任预计算比例字段。
聚合计数是提交级统计；除非文档明确分母一致，不得与消息级发送日志相减或合并。

`TotalSendCount` 作为服务端报告的发送量单独展示，不能替代号码数、提交数或任何
比例分母。只有全部字段存在且数值一致时，未回执数才能计算为
`TotalSendSuccessCount - TotalReceiptSuccessCount -
TotalReceiptFailureCount`。字段缺失、分母为零或计数不一致时返回
`insufficient_data`。

分析窗口必须显式提供、精确到秒，按 Asia/Shanghai 解释为 `[start, end)`，
最长 90 天。Action 请求使用 Unix 秒时间戳，因此每次请求的 `EndTime` 传入该
窗口结束时刻前 1 秒。小时/天趋势使用固定本地边界，聚合请求最多 100 次。

`ChannelType` 只限定聚合统计。它不能与发送日志分析组合，因为
`ListSmsSendLogForAgent` 没有对应的 `ChannelType` 请求过滤条件，否则会混合
不同数据范围。`Mobile` 过滤要求启用发送日志分析，且不得在记录中回显。报告范围
使用 `sendLogsMobileFilterApplied` 命名，避免误认为聚合过滤；聚合趋势仍只受
聚合 Action 支持的维度限定。

### 官方公开错误码文档

保留公开错误码原值，并在运行时查询最新火山引擎短信官方文档：

- [发送接口错误码](https://www.volcengine.com/docs/6361/173288?lang=zh)：
  `RE:*` 等实时发送/API 错误；
- [发送状态错误码](https://www.volcengine.com/docs/6361/173291?lang=zh)：
  `CR:*`、`CE:*`、`NE:*`、`SY:*`、`UN:*` 等异步回执错误。

不要把错误说明硬编码到 Skill。官方页面不存在精确错误码时，说明未找到公开解释，
并建议客户携带客户可见 Message ID 和 Request ID 联系支持。不得推断或输出
非公开实现原因。

除 `ListSmsSendLogForAgent` 外，每个 Action 都公开通用错误码 `1001`、`1015`、
`1023`、`1024`、`1999`、`RE:0000`、`RE:0001`、`SY:0500`。
`ListSmsSendLogForAgent` 公开 `1001`、`1999`、`RE:0000`、`RE:0001`、
`SY:0500`。其他 Action 专属错误码如下：

| Action | 额外错误码 |
| --- | --- |
| `ApplySmsSignatureV2` | `1003`、`1008`、`1009`、`1027`、`1029`、`1030` |
| `ApplySmsTemplateV2` | `1007`、`1009`、`1028` |
| `SetBatchTask` | `1007`、`1009` |
| `TemplateUploadDemo` | `1007`、`1009` |
| `GetSubAccountDetail` | `1009` |
| `GetBatchTaskList` | `1009` |
| `GetBatchTaskDetail` | `1009` |
| `ConsentBatchTask` | `1009` |
| `DeleteBatchTask` | `1009` |

仅对查询操作，`1015` 与 `1999` 属于瞬时错误，与 HTTP 429/5xx 共用同一有界
退避预算。写操作即使返回这两个码也只能发送一次，并按对账规则处理。

## 申请契约

### ApplySmsSignatureV2

Skill 必填输入：

- `content`：不带括号的签名文本
- `purpose`：`1` 自用，`2` 他用
- `source`：整数枚举 `1 = 公司`、`2 = App`、`3 = 商标`
- `signatureIdentificationID`：属于当前调用方且已审核通过的资质
- `subAccounts`：客户明确指定的消息组子集；客户不确定或未指定时使用全部可见
  消息组
- 明确的 `channelTypes`：`CN_OTP`、`CN_NTC`、`CN_MKT` 中的一种或多种

可选字段包括 `desc`、`domain`、`scene`、`projectName`、`appIcp`、
`trademark`。`appIcp` 是 JSON 对象，只包含字符串 `appIcpFilling`；
`trademark` 是 JSON 对象，只包含字符串 `trademarkCn`、`trademarkEn`、
`trademarkNumber`。仅 `source=2` 可发送 `appIcp`，仅 `source=3` 可发送
`trademark`，公司来源 `1` 两者都不接受。不要发送 `uploadFileList`；
本 Skill 不收集资质申请材料。

结果只允许 lower-camel 字段 `applyId`、`status`、`reason`。

服务端可能把省略的短信类型默认扩展为全部，因此 Skill 绝不能省略客户选择。
默认全选消息组时，提交前重新查询；集合变化后必须重建预览。

### ApplySmsTemplateV2

Skill 必填输入：

- `content`
- `channelType`
- 固定为 `cn` 的 `area`
- `name`
- `signatures`
- 明确的 `subAccounts`
- 与内容变量一致的 `templateParams`

可选字段包括 `project`、`desc`、`shortUrlConfig`。已发布 Action 不包含
`callbackUrl`。`shortUrlConfig` 只接受字符串 `isEnabled`、`belong`、
`isNeedClickDetails` 和整数 `uaCheckStrategy`。短链选项仅适用于符合要求的营销
模板。验证码模板至少需要一个普通变量，不能使用特殊引流参数。

结果只允许 lower-camel 字段 `templateId`、`status`、
`statusDescription`、`auditOpinion`。

选择消息组前，必须根据完整内容判断 `channelType`。对所选签名绑定的每个消息组，
使用 `GetSubAccountDetail.channelTypeToIndustryConfig` 查找该短信类型对应
行业。所有可用消息组行业相同时选择一个代表消息组；行业不同时，在生成申请预览前
询问客户使用哪个行业。

## 单条发送契约

### 单条发送预检与模板匹配

`match-template` 是只读工作流，接收完整客户内容、规范化签名、所选消息组，以及
根据内容判断的短信类型。先按签名和消息组缩小候选，再使用
`ListSecondTemplate` 获取详情。匹配模板必须状态为 `3` 或 `5`，短信类型相同，
消息组与签名关系相同，且内容逐字节完全一致。不要选择相似模板。没有符合项时返回
无匹配；存在多个符合项时，按确定顺序返回候选 ID。

单条发送预检只要求：

- 所选消息组状态为 `1`；
- 签名状态为 `3` 或 `5`，且绑定该消息组；
- 模板状态为 `3` 或 `5`，且按同一签名和消息组过滤；
- 已解析模板内容与模板变量集合完全一致。

预检不调用 `GetSignatureIdentificationList`，不要求签名资质 ID，不要求
`ListSignatureForAgent` 返回 `usable` 或 `ChannelTypes`，也不使用
`GetSubAccountDetail` 校验消息组行业。但明确的签名 `usable=false` 仍必须
拒绝发送。

### SendSmsForAgent

必填 Body 字段：

- `SubAccount`
- `Signature`
- `TemplateId`
- `Mobiles`：逗号分隔的国内手机号

可选字段：`TemplateParam`，编码为紧凑 JSON 字符串。不得发送 `Account`。

结果包含 Message ID。API 成功只表示提交已接受，不表示回执已完成。

## 群发契约

### GetUploadTosURL

GET 字段：`suffix`，只允许 `csv`。结果包含：

- `file`：作为 `fileUrl` 使用的不可变 TOS 对象 Key
- `url`：五分钟有效的预签名上传 URL

使用 HTTP PUT 上传文件到 `url`。输出或日志中绝不能包含 URL 查询参数。
Skill 只在当前命令中记录本地 SHA-256，不持久化文件或摘要。只接受
`.volces.com` 下的 HTTPS 火山引擎 TOS Host；拒绝 userinfo、fragment 和
重定向。

### TemplateUploadDemo

POST 字段：`subAccount`、`templateId`，以及可选 `forceUpdate`。使用响应确定
精确的 `phone` 列和模板变量列。成功响应可能是
`application/octet-stream` CSV 文件流，而不是 JSON。
`TemplateUploadDemo` 是唯一允许成功返回非 JSON 的 Action；其他 Action 必须
继续执行仅 JSON 校验。只返回安全文件名、解码后的 CSV 内容、Content-Type 与
字节数。

### SetBatchTask

必填 Body 字段：

- `subAccount`
- `name`
- `signature`
- `templateId`
- `templateName`
- `channelType`
- `scheduled`
- `sendTime`
- `fileUrl`
- 对象 `extra`

结果包含 `taskId`、`dupCount`、`totalCount`。创建时由服务端校验文件，绝不能
自动调用 `ConsentBatchTask`。CLI 还会把本地文件/内容哈希与预检统计作为会话
交接信息返回；不得把它们加入服务端 `extra` 结构。

固定模板必须保留明确的空模板变量列表。同一主模板在 `ListSecondTemplate`
返回多条记录时，选择绑定目标消息组的记录。按签名限定的查询允许省略冗余模板签名
关系；返回关系时必须匹配。公开模板响应缺少展示名时，把权威模板 ID 作为
`templateName`。

### GetBatchTaskDetail

GET 字段：`subAccount`、`taskId`。已知任务 ID 时，该 Action 是权威对账来源。
创建成功后查询详情获取真实状态；详情不可用时返回 null/unknown，不要臆造
`Valid(2)`。创建响应丢失且未知 `taskId` 时，当前契约无法安全对账。

任务详情不保证保存 CLI 的本地文件 SHA-256 或全部预检统计。详情缺失时，启动
预览必须使用群发创建阶段保留的交接信息，不得臆造。

已知任务状态：

| 值 | 名称 | 含义 |
| --- | --- | --- |
| 0 | Init | 已初始化 |
| 1 | Draft | 未完成草稿 |
| 2 | Valid | 已校验，等待授权 |
| 3 | Consented | 已接受启动 |
| 4 | Preparing | 正在准备收件人 |
| 5 | Sending | 正在发送 |
| 6 | Done | 成功终态 |
| 7 | Canceled | 已取消终态 |
| 8 | Failed | 失败终态 |
| 9 | Killed | 强制终止 |

未知数值必须原样保留，不要臆造标签。

### GetBatchTaskList

必填 GET 字段：`subAccount`、`pageIndex`、`pageSize`。可选过滤字段为
`taskName`、`signature`、`templateId`。

已校验但未授权的状态 `2` 任务可能不出现在列表中。创建后始终交接
`taskId + subAccount`，并使用详情查询。

### ConsentBatchTask

POST 字段：`subAccount`、`taskId`。只有最新详情状态为 `2`，且客户已经使用
`确认启动任务 <taskId>` 授权完全相同的任务摘要时，才能调用。

### DeleteBatchTask

POST 字段：`subAccount`、`taskId`。只有最新任务状态和定时发送窗口允许取消时
才能调用。定时任务进入 `sendTime` 前一分钟截止区间后必须拒绝；最终以服务端
判断为准。响应丢失时通过任务详情对账。

## 重试与错误契约

- 凭证或权限错误：立即停止。
- 参数、校验、审核拒绝、冲突和公开 4xx 错误：不要重试。
- 查询 Action：连接失败、HTTP 429、可重试 5xx 和公开瞬时业务码
  `1015`/`1999` 最多重试两次，并使用有上限的指数退避；HTTP 响应存在
  `Retry-After` 时，在上限内遵循。
- 写 Action：不要自动重试。
- HTTP 200 但包含 `ResponseMetadata.Error` 时仍视为失败。
- 递归脱敏后保留公开错误码和 Request ID。
