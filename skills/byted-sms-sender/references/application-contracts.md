# 资质、签名与模板申请契约

## 资质向导 Action

资质网络调用全部使用 `2026-01-01` Agent Action，并遵循
[qualification-materials.md](qualification-materials.md) 的输出边界：

| 能力 | Action | 关键边界 |
| --- | --- | --- |
| 账号主体 | `ListAllSmsProduct` | 读取 `businessName`、`userType` |
| 上传凭证 | `GetMUploadParam` | 凭证只在进程内使用 |
| OCR | `GetOCRLicenseForAgent` | 图片地址隐藏 |
| 账号规则 | `GetAccountIdentRankForAgent` | 只返回必填规则 |
| 企业校验 | `ThreeElementEnterpriseCheckForAgent` | ticket 隐藏 |
| 联系人校验 | `ThreeElementPersonCheckForAgent` | ticket 隐藏 |
| 发送验证码 | `SendSmsVerifyCodeByMobile` | 写请求只发送一次 |
| 校验验证码 | `CheckSmsVerifyCodeByMobile` | 写请求只发送一次 |
| 创建资质 | `ApplySignatureIdentificationForAgent` | 写请求只发送一次 |

营业证件、经办人和独立责任人必须对应当前草稿执行校验。企业不匹配可使用服务端约定
的人工审核标识；经办人或独立责任人不匹配时必须修改信息。责任人与经办人相同时复用
经办人 ticket。

`GetMUploadParam` 返回的临时 AK/SK/Session Token 不能作为客户凭证，不得写入文件、
环境变量、命令参数、日志或对话。ImageX 使用平台固定服务，客户无需提供 ImageX
凭证。

`purpose=1` 为自用；`purpose=2` 为他用。仅当账号规则返回
`needOtherUseCheck=true` 时，他用资质提交一张 `powerOfAttorney`，`fileType=5`；
否则不收集、不发送。他用资质先调用 `ListAllSmsProduct`；授权方使用营业证件名称，
被授权方使用返回的 `businessName`，两者不得手填或修改。

`ListAllSmsProduct.userType=smb` 时，经办人或独立责任人填写手机号后，在人员信息校验
通过后还需完成手机号验证码校验；`sameOperator=true` 时责任人复用经办人的验证结果。
发送验证码使用 `appId=482875`、`scene=3`、`codeType=0`、`channelId=2430`，生产模板
ID 为经办人 `59030`、独立责任人 `59029`；同一人不再次发码。校验验证码使用
`appId=482875`、`scene=3`、`func=2`；结果 `status=0/1/2` 分别表示正确、错误、过期。
验证码不得由本机服务回显、写入日志或进入最终资质提交参数。

## 资质列表

`GetSignatureIdentificationList` Body 必填整数 `pageIndex`、`pageSize`；可选整数
`id`、字符串 `materialName` 和可重复整数 `status`。只使用：

- `id`、`purpose`、`materialName`、`businessCertificateName`
- `effectSignatures`
- `auditStatus`、`auditOpinion`、`auditedAt`
- `usable`、`isOrder`

不得返回联系人、证件号、手机号、材料地址或原始业务材料。签名申请只选择
`usable=true` 且审核通过的资质。

## 消息组详情

`GetSubAccountDetail` 必填 GET 字段 `subAccount`，不得发送 `Account`。只使用
`subAccountId`、`subAccountName`、`status` 和
`channelTypeToIndustryConfig`；映射项限于 `channelType`、`channelTypeCn`、
`industry`、`industryCn`。行业用于模板申请解释，不是签名申请门禁。

## 签名列表与申请

`ListSignatureForAgent` Body 可选 `Signature`、`SubAccounts`，并传 `Page`、
`PageSize`。比较前移除外围签名括号。状态 `3`、`5` 表示审核通过或免审，`2` 表示
拒绝；明确 `usable=false` 必须拒绝。

`ApplySmsSignatureV2` 必填：

- `content`：无外围括号的签名文字
- `purpose`：`1` 自用、`2` 他用
- `source`：`1` 公司、`2` App、`3` 商标
- `signatureIdentificationID`
- 明确的 `subAccounts` 和 `channelTypes`

可选 `desc`、`domain`、`scene`、`projectName`、`appIcp`、`trademark`。只有
`source=2` 接受 `appIcp`，只有 `source=3` 接受 `trademark`；不要发送
`uploadFileList`。结果只使用 `applyId`、`status`、`reason`。默认全选消息组时，
提交前重新查询；集合变化后重新预览。

## 模板申请

`ApplySmsTemplateV2` 必填 `content`、`channelType`、固定 `area=cn`、`name`、
`signatures`、明确的 `subAccounts` 以及与内容变量一致的 `templateParams`。可选
`project`、`desc`、`shortUrlConfig`，不发送 `callbackUrl`。`shortUrlConfig` 只接受
`isEnabled`、`belong`、`isNeedClickDetails`、`uaCheckStrategy`。

根据完整内容判断：验证码 `CN_OTP`、通知 `CN_NTC`、营销 `CN_MKT`。对签名绑定的
可用消息组查询详情；行业一致时选代表消息组，不一致时让客户选择。结果只使用
`templateId`、`status`、`statusDescription`、`auditOpinion`。

签名和模板申请额外错误码：

| Action | 错误码 |
| --- | --- |
| `ApplySmsSignatureV2` | `1003`、`1008`、`1009`、`1027`、`1029`、`1030` |
| `ApplySmsTemplateV2` | `1007`、`1009`、`1028` |
