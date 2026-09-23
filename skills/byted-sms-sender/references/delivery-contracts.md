# 模板、发送、群发与分析契约

## 模板查询与精确匹配

`ListBatchTemplatesForAgent` 查询当前账号的群发模板目录；`list-templates` 使用该接口。
`ListSmsTemplateForAgent` 保持普通模板查询语义，用于单条发送和模板状态查询。

`ListBatchTemplatesForAgent` Body 可选 `TemplateId`、`SubAccounts`、`Signatures`，并传
`Page`、`PageSize`。返回 Total/List，模板正文为 TemplateContent，SubAccounts 为适用消息组；
Description 为用途说明，TaskFields 为可选的任务输入定义；缺失或为空时无需任务级字段。
BatchOnly 为布尔值，默认 false；true 表示仅支持群发任务发送。

CLI `list-templates` 默认收齐分页。可选 `--keyword` 按名称、正文和用途说明做字面匹配，
可重复传入，保留命中任一关键词的候选、审核状态及接口顺序；语义适配由 Agent 判断。
筛选后的 Total 为候选数，ScannedTotal 为实际读取的模板数。仅排查单页响应时指定
`--page`；关键词匹配使用完整分页。

`ListSecondTemplate` GET 字段为 `project`、`templateId`、`secondTemplateId`、`signatures`，
用于查看各二级模板的审核状态、行业、参数及关联范围；`createdAt`、`updatedAt` 为 Unix 秒。
Agent 可直接查询列表和详情，也可使用 `match-template` 辅助比较普通模板正文。
该命令必填 `--content`、`--signature`、`--sub-account`，可选 `--channel-type`；
省略短信类型时比较所有类型。`candidates` 按一级模板 ID 返回，`templateRecords` 为原始记录，
`matchingRecords` 为正文及指定短信类型命中的记录，保留变量定义、行业和审核状态。
`complete=false` 表示查询未完成，已有候选仍可参考，结合 `errors` 决定是否补查；
完整查询的 `classification=none/single/ambiguous` 分别表示命中零个、一个或多个模板。
内容匹配不代表可以发送，模板选择由 Agent 结合客户用途和接口返回判断。

## 单条发送

`SendSmsForAgent` Body 必填 `SubAccount`、`Signature`、`TemplateId`、逗号分隔的
`Mobiles`；可选 `TemplateParam` 紧凑 JSON 字符串，账号身份由请求鉴权提供。结果包含
Message ID，只表示提交已接受。

`TemplateParam` 与当前模板变量集合一致；群发表单试发见 [batch-form.md](batch-form.md)。

发送准备按模板返回的 `SubAccounts` 选择消息组。具体 ID 表示模板的适用范围；
`All` / `*` 表示全消息组范围，此时调用 `GetSubAccountListForAgent`，从当前账号启用的消息组中选取实际 ID。
已有目标 ID 时可传 `subAccount` 精确筛选；需要展示名称和状态时也使用该列表。
短信类型读取模板的 `ChannelType`，最终发送约束由提交接口校验。
普通模板调用现有 GET 接口 `ListSecondTemplate`：

```json
{"templateId":"template-id","signatures":"示例企业","subAccounts":["group-id"]}
```

返回 `list`；每条保留 `secondTemplateId`、`industry`、`reviewStatus`、`reason`、
`subAccounts`、正文 `content` 和变量定义 `templateParams`。预览展示查询到的正文，
审核情况按每条记录的行业和状态分别解释。多条记录的正文、变量定义及短信类型一致时共用一个内容预览；
存在差异时说明歧义，先核对各条记录。空结果说明当前查询未取得预览依据。
列表中的审核状态用于说明该记录的审核进度；发送提交后，根据服务端返回的 Message ID 或业务错误继续处理。

## 发送日志与统计

统计与发送记录默认查询当前主账户下全部消息组的数据。只有客户明确限定消息组或项目时，
才传相应筛选；主账户身份由鉴权确定。统计省略 `SmsAccount`、`Project`，记录省略
`SubAccount` 即为主账户范围。

发送记录使用 `ListSmsSendLogForAgent`，Body 传 `Page`、`PageSize`；
按需传 `MessageId`、`SubAccount`、`FromTime`、`ToTime`、`Mobile`、`TemplateId`、`Signature`。
请求时间为 Unix 秒，返回 `SendTime`、`ReceiptTime` 为 Unix 毫秒。
`send-status` 传 `--message-id`，时间范围使用可选的 `--from-time`、`--to-time`。

保留返回的 `ErrorCode`、`ErrorType`、`ErrorMessage`、`ChannelType`、发送和回执时间。
当前接口未提供 `Status` 时，显示“状态未知”，并展示已有时间和错误信息；
接口明确返回 `Status` 时读取其原值：1 等待回执，2 失败，3 成功回执。
试发轮询使用本次请求开始时间至当前时间，并精确匹配 `MessageId`。
完整手机号和短信正文留在私密处理流程。

`GetTotalSendCountStatV4ForAgent` 直接查询聚合统计，参数由 Agent 按需要填写：

| 参数 | 含义 |
| --- | --- |
| `StartTime`、`EndTime` | Unix 秒，最长 90 天，时间口径见下文 |
| `Project`、`SmsAccount` | 项目与消息组，字符串 |
| `ChannelType`、`Signature`、`TemplateId` | 短信类型、签名、模板，字符串数组 |
| `StandardErrorCode` | 失败错误码数组，不传空字符串或成功码 `0` |
| `IsDomestic` | 国内为 `1` |
| `NotSplit` | `false` 为拆分条数，`true` 为未拆分条数；明确本次统计口径 |
| `DateGroup`、`SmsAccountGroup`、`ChannelGroup`、`SignatureGroup` | 按日期、消息组、短信类型、签名分组，`1` 开启 |
| `TemplateIdGroup`、`StandardErrorCodeGroup` | 按模板、失败错误码分组，`1` 开启 |

时间按 Asia/Shanghai。昨天零点起的实时数据使用 `[StartTime,EndTime)`，结束时间直接传入；
更早的数据只有日粒度，按首尾日期查询，整日范围传首日 `00:00:00` 至末日 `23:59:59`。
历史数据按完整自然日展示，历史小时或不完整日期的请求需说明实际覆盖粒度。
跨越两种数据粒度时分别说明各段的实际范围。

返回 `DataPoints`、`DataPointsByDate` 及总量，直接使用服务端字段与分组进行汇总解释。按模板或错误码分析使用对应 Group 参数，记录分页只用于消息级证据。
`Count` 缺失时保持未知。

提交成功率为 `TotalSendSuccessCount / TotalAllSendCount`，回执成功率为
`TotalReceiptSuccessCount / TotalSendSuccessCount`；展示比例时说明分子和分母。
`TotalSendCount`、`TotalNoReceipt72HourCount` 按接口含义单独展示。
分母为零、字段缺失或查询未覆盖全部分页时说明数据限制。聚合条数与消息记录数量口径不同。

## 群发上传与任务

操作步骤见 [batch-form.md](batch-form.md)。

`GetUploadTosURL` GET 字段 `suffix=csv`，结果 `file` 是文件 Key，`url` 是五分钟
预签名地址。只接受 `.volces.com` HTTPS Host；拒绝 userinfo、fragment 和重定向，日志
不得包含 URL 查询参数。

`TemplateUploadDemoForAgent` POST 字段为 `subAccount`、`templateId`。
成功返回 CSV 文件流；按其表头准备名单，与模板变量不一致时先核对模板。

群发文件上限为 1,000,000 个手机号和 50 MB。定时任务必须在未来一个月内，并位于
Asia/Shanghai 的 08:00–21:30。取消以最新任务状态和
服务端响应为准，进入发送前一分钟截止区间后拒绝。

`ValidateBatchTaskContentForAgent` POST 字段为 subAccount、signature、templateId 和
content。模板 TaskFields 声明任务级正文时自动预检；`batch-content-check` 可单独调用。
保留正文原文及返回的 Approved、Reason、Request ID；Approved 为布尔 true 才通过，false 时按原因修改。
正文由客户最终确认，编辑后重新预检；逐行变量由文件承载。

`SetBatchTaskForAgent` 接收 subAccount、name、signature、templateId、scheduled、
sendTime、fileUrl、idempotencyKey，按 TaskFields 选填 content。idempotencyKey 由脚本为本次提交
生成；服务端占位成功后保留一小时，成功或失败均不释放，同 key 重复提交失败。
明确拒绝后修正参数会生成新提交标识；超时或结果未知时先对账，不换 key 重建。
结果为 taskId、totalCount、dupCount；
缺失计数不从本机统计补齐。创建和确认的操作顺序见 [batch-form.md](batch-form.md)。

`GetBatchTaskDetail` GET 字段 `subAccount`、`taskId`，是已知任务 ID 的权威对账来源。
`GetBatchTaskList` 必填 `subAccount`、`pageIndex`、`pageSize`，可选 `taskName`、
`signature`、`templateId`；状态 `2` 任务可能不在列表中。

| 状态 | 含义 |
| --- | --- |
| `0` | 已初始化 |
| `1` | 草稿 |
| `2` | 已校验，待授权 |
| `3` | 已接受启动 |
| `4` | 正在准备 |
| `5` | 正在发送 |
| `6` | 任务处理完成，不代表逐条送达 |
| `7` | 已取消 |
| `8` | 失败 |
| `9` | 强制终止 |

`ConsentBatchTask` 与 `DeleteBatchTask` 都传 `subAccount`、`taskId`。启动只允许最新状态
`2` 且客户确认完全相同的摘要；取消需重新查询状态并检查发送窗口。二者响应丢失时只
通过任务详情对账。
