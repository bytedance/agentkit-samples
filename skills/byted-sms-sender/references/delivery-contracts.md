# 模板、发送、群发与分析契约

## 模板查询与精确匹配

`ListSmsTemplateForAgent` Body 可选 `TemplateId`、`SubAccounts`、`Signatures`，并传
`Page`、`PageSize`。响应可能使用单数 `Signature` 或复数 `Signatures`；存在任一
结构时都必须与目标签名一致，同时返回但互不相交时返回 `contract_conflict`。

`ListSecondTemplate` GET 字段为 `project`、`templateId`、`secondTemplateId`、
`signatures`。列表缺少名称、内容、变量或消息组关系时，用它获取详情。模板必须状态
`3`/`5`，内容逐字节一致，变量名集合、签名、消息组和短信类型全部一致；相似模板不能
替代。`createdAt`、`updatedAt` 是 Unix 秒。

## 单条发送

`SendSmsForAgent` Body 必填 `SubAccount`、`Signature`、`TemplateId`、逗号分隔的
`Mobiles`；可选 `TemplateParam` 紧凑 JSON 字符串，不发送 `Account`。结果包含
Message ID，只表示提交已接受。

发送前只校验：消息组状态 `1`；签名状态 `3`/`5` 且绑定消息组；模板状态 `3`/`5`
且按签名和消息组过滤；解析内容与变量完全一致。明确 `usable=false` 必须拒绝；不要为
单条发送额外查询资质或行业。

## 发送日志与统计

`ListSmsSendLogForAgent` Body 必填 `SubAccount`、`Page`、`PageSize`，可选
`FromTime`、`ToTime`、`Mobile`、`TemplateId`、`Signature`、`MessageId`。
手机号只用于过滤，响应不得返回。请求时间是 Unix 秒，`ToTime` 使用区间结束前 1 秒；
响应 `SendTime`、`ReceiptTime` 是 Unix 毫秒。按 Message ID 去重。

非空且非成功标记的公开错误码计失败；有回执时间且无失败码计成功；二者都无计未回执。

`ListTotalSendCountStatForAgent` 必填 `StartTime`、`EndTime`，可选 `SubAccount`、
`ChannelType`、`Signature`、`TemplateId`。提交成功率使用
`TotalSendSuccessCount / TotalAllSendCount`，回执成功率使用
`TotalReceiptSuccessCount / TotalSendSuccessCount`。展示字段名、分子、分母和百分比，
不信任预计算比例。聚合统计与消息日志分母不同，不相减或合并。

`TotalSendCount` 仅作为服务端报告的发送量单独展示，不能替代号码数、提交数或比例
分母。不要同时使用 `ChannelType` 与 `--include-logs`：发送日志没有短信类型过滤条件，
两条分支的数据范围不同。

分析窗口按 Asia/Shanghai 的 `[start,end)`，最长 90 天；分母为零、字段缺失、计数矛盾
或分页截断时返回 `insufficient_data`。

## 群发上传与任务

`GetUploadTosURL` GET 字段 `suffix=csv`，结果 `file` 是不可变对象 Key，`url` 是五分钟
预签名地址。只接受 `.volces.com` HTTPS Host；拒绝 userinfo、fragment 和重定向，日志
不得包含 URL 查询参数。

`TemplateUploadDemo` POST 字段 `subAccount`、`templateId` 和可选 `forceUpdate`。
它是唯一允许成功返回 CSV 文件流而非 JSON 的 Action。

群发文件上限为 1,000,000 个手机号和 50 MB。定时任务必须在未来一个月内，并位于
Asia/Shanghai 的 08:00–21:30；不假设账号存在特殊时段例外。取消以最新任务状态和
服务端响应为准，进入发送前一分钟截止区间后拒绝。

`SetBatchTask` 必填 `subAccount`、`name`、`signature`、`templateId`、`templateName`、
`channelType`、`scheduled`、`sendTime`、`fileUrl`、`extra`。结果包含 `taskId`、
`dupCount`、`totalCount`；创建时禁止调用 `ConsentBatchTask`。

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

群发相关额外错误码：`SetBatchTask`、`TemplateUploadDemo` 使用 `1007`、`1009`；
任务详情、列表、启动和取消使用 `1009`。
