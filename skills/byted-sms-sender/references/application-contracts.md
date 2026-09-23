# 资质、签名与模板申请契约

资质材料通过 [私密向导](qualification-materials.md) 办理。

## 资质与消息组

`GetSignatureIdentificationList` Body 传整数 `pageIndex`、`pageSize`，可选整数 `id`、
字符串 `materialName`、整数数组 `status`。返回 `list` 和 `total`。当前后端先取最多 500 条候选再筛选分页，展示总数时说明这一查询范围。
审核状态 `1` 为审核中、`2` 为拒绝、`3` 为通过；申请签名选择审核通过且 `usable=true` 的资质。
例如查询可选资质：

```json
{"pageIndex":1,"pageSize":100,"status":[3]}
```

结合 `total` 继续分页；保留企业信息、审核意见、更新单、可重提标记和可用性等业务字段，缺失时标为未知。

消息组列表使用 `GetSubAccountListForAgent`，传 `pageIndex`、`pageSize`，可选 `subAccountName`、
`subAccount`、`project`、`allStatus`。默认查询启用组，`allStatus=true` 查询全部状态。
返回 `list/total`，ID 是 `subAccountId`，状态为 `status`，创建时间为 `createdTime`。
`list-message-groups` 默认读取完整分页；可用 `--name`、`--page`、`--page-size`、`--all-status`。
用户指定停用或删除状态时，先查询全部状态，由 Agent 按返回的 `status` 解释。

消息组详情使用 `GetSubAccountDetail`，GET 参数为 `subAccount`。
用户需要查看完整消息组详情时使用，返回 `subAccountId`、`status` 和 `enabledChannelType[].value`；
`channelTypeToIndustryConfig` 提供对应的行业配置。账号身份由请求鉴权确定。
发送时按 [发送契约](delivery-contracts.md) 选择消息组。

## 预览与提交

签名使用 `signature-preview` / `signature-submit`，模板使用 `template-preview` /
`template-submit`，通过 `--params '<JSON>'` 传入接口原生参数。preview 只返回本地整理的原参数与
`digest`，用于客户核对本次申请；客户确认后，submit 传相同参数及 `--preview-digest <digest>`。
服务端校验业务规则；提交返回资源 ID 或包含错误码、说明和 Request ID 的错误。
结果未知时保留诊断标识，通过资源查询核实。

## 签名列表

查询签名、短信类型、行业、审核状态或消息组适用范围时，使用 `ListSignaturesForAgent`。
它返回分页的二级签名列表：同一“签名＋短信类型＋行业＋审核状态”合并为一行，
同组的消息组合并到 `SubAccounts`；项目和消息组用于筛选查询范围。
按短信类型、行业、审核状态和消息组范围逐行展示结果。
指定完整签名时传 `ExactMatch=true`；只传用户要求的筛选条件，查询全部审核状态时不传 `Statuses`：

```json
{"action":"ListSignaturesForAgent","params":{"Signature":"示例企业","ExactMatch":true,"Page":1,"PageSize":100}}
```

CLI：`list-signatures --signature 示例企业 --exact-match`，支持 `--project`、重复传入的
`--sub-account`、`--channel-type`、`--industry`、`--status`，以及 `--page`、`--page-size`。
请求必填 `Page`（从 1 开始）和 `PageSize`（1–100）；可选 `Signature`、`ExactMatch`、
`ProjectName`、`SubAccounts`、`ChannelTypes`、`Industries`、`Statuses`。后四项为数组，
`Statuses` 的元素为整数，其余数组元素为字符串。未指定精确匹配时，签名按前缀查询。
查询当前账号范围时省略项目和消息组；`Total` 大于已读取条数时继续分页，完成后说明实际覆盖范围。

返回 `List`、`Total`；每项包含 `Signature`、`Industry`/`IndustryLabel`、
`ChannelType`/`ChannelTypeLabel`、`SubAccounts`、`Status`/`StatusDescription`、
`AuditOpinion`、`Usable`、`OrderID`、`MaterialID`、`IdentificationName`、`CreatedAt`、`UpdatedAt`。
`SubAccounts=[]` 表示该行业和短信类型下适用于全部消息组，非空时展示返回的消息组范围。
`OrderID` 保留字符串，时间为 Unix 秒；审核意见为空时标明接口未提供原因。
常见状态 `1` 审核中、`2` 拒绝、`3` 通过、`5` 免审、`16` 等待资质审核通过。
`Usable` 表示这一行业和短信类型审核通过或免审；运营商报备和发送结果通过各自查询结果说明。
签名列表用于资源查询和状态解释；发送准备读取模板查询结果，提交结果由发送接口返回。

## 签名申请

`ListSignatureForAgent` Body 可选 `Signature`、`SubAccounts`，并传 `Page`、`PageSize`。
签名文字使用去掉外围括号的名称。状态 `3`/`5` 为审核通过/免审，列表汇总状态用于展示，
逐条说明其行业、短信类型及关联范围。`SubAccounts` 为空或包含 `*` / `All`
时表示全消息组范围。发送准备按模板、签名和消息组查询现有模板记录，见
[发送契约](delivery-contracts.md)。

`ApplySmsSignatureV2` 参数示例（ID、签名和消息组替换为本次查询与确认的值）：

```json
{
  "content":"示例企业",
  "purpose":1,
  "source":1,
  "signatureIdentificationID":123,
  "subAccounts":["group-id"],
  "channelTypes":["CN_NTC"]
}
```

`signatureIdentificationID` 是整数；`subAccounts`、`channelTypes` 是字符串数组。
`purpose`：`1` 自用、`2` 他用；`source`：`1` 公司、`2` App、`3` 商标。
可选字符串 `desc`、`domain`、`scene`、`projectName`。App 来源可填
`appIcp:{"appIcpFilling":"备案号"}`；商标来源可填
`trademark:{"trademarkCn":"中文名","trademarkEn":"英文名","trademarkNumber":"注册号"}`。
资质引用已有 `signatureIdentificationID`，材料由私密向导办理。
返回 `applyId`、`status`、`reason`；后续审核状态通过签名列表查询。

## 模板申请

短信类型按完整内容的发送目的选择：`CN_OTP` 用于身份验证，`CN_NTC` 用于已发生或
约定事项的事务通知，`CN_MKT` 用于商品、服务、优惠等推广营销。

申请模板时按本次用途填写 `signatures`、`subAccounts`、`channelType`，有项目范围时填写 `project`。
`ApplySmsTemplateV2` 根据账号、消息组或项目范围、短信类型和关联账号校验签名资格。
失败时根据错误码和原因补充签名关联、资质或参数，再重新预览确认。

`ApplySmsTemplateV2` 参数示例：

```json
{
  "content":"您预约的服务时间为${time}，请准时到店。",
  "channelType":"CN_NTC",
  "area":"cn",
  "name":"预约提醒",
  "signatures":["示例企业"],
  "subAccounts":["group-id"],
  "templateParams":[{"name":"time","paramType":1}]
}
```

`signatures`、`subAccounts` 是字符串数组；`templateParams` 是对象数组，每项 `name`
对应正文 `${name}` 中的变量名，普通变量的整数 `paramType=1`。无变量时传 `[]`。
可选字符串 `project`、`desc`。可选 `shortUrlConfig` 中 `isEnabled`、`belong`、
`isNeedClickDetails` 为字符串，`uaCheckStrategy` 为整数。
返回 `templateId` 后，按需用 `ListSmsTemplateForAgent` 查询审核状态；核实正文、变量与
适用范围使用 `ListSecondTemplate`。群发候选目录用于选择发送模板，申请进度以审核查询为准。

申请额外错误码：签名 `1003`、`1008`、`1009`、`1027`、`1029`、`1030`；
模板 `1007`、`1009`、`1028`。公共错误处理见 [actions.md](actions.md)。
