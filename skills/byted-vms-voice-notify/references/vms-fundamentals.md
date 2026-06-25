# 火山通信 TOP 调用基础知识

> 本文档是 `vms-*` 系列 Skill 的**本地基础参考**, 由飞书原文 (火山通信基础知识 for top
> invoke) 抽取而来, 仅保留 Agent 调 TOP 接口必需的概念 / 字段 / 取值, 不含图片.
> 任何 SKILL.md 在拼装请求体前都应先读这里.
>
> 飞书原文 (可选, 仅当本文档遗漏时回看):
> https://bytedance.sg.larkoffice.com/docx/Mv32dc0yooBn7txDxW8lsDdDgYb

## 1. 基础概念

- **AccountId (账户)**: 火山引擎账号唯一标识, 不同客户互相隔离, 多租户.
- **ServiceType (服务)**: 火山通信定义的顶层服务类型.
  - `100` 普通语音
  - `200` 隐私号
- **SubServiceType (子服务)**: 一个 AccountId 下只能开通一种子服务,
  必须先在控制台开通对应子服务才能调相关接口.
  - 隐私号系列:
    - `201` AXB
    - `202` AXN
    - `203` AXNE
    - `204` AXYB
    - `205` PAXYB
    - `206` AXG
  - 语音 SIP 系列:
    - `101` 语音 SIP
    - `102` 语音通知
    - `103` 双呼
    - `104` 智能外呼
    - `105` 双呼 lite
    - `106` 双呼 mobile
    - `107` 云联络中心
    - `108` 号码托管
- **NumberPoolNo (号码池)**: 每个子服务下可创建多个号码池, 是号码的管理集合.
  隐私号选号 / 语音通知主叫绑定都按号码池维度操作.

> 注: 部分 SKILL.md 简化文档把语音通知 / 隐私号 / 智能外呼分别记作 SubServiceType
> `102 / 101 / 103`. **以本文档为准**: 隐私号是 201~206, 语音通知 102, 智能外呼 104.
> 调接口时若用 SubServiceType 字段, 严格按本表传值.

## 2. 用户开通流程

调用 TOP 写接口前需保证已完成两步:

1. **开通服务**: 首次访问 https://console.volcengine.com/cloud_vms 时, 勾选协议
   并点击 "开通服务", 后台会创建 bytesbc 账户.
2. **开通子服务**: 在控制台 "服务开通" 页选择具体子服务 (如语音通知 / AXB 等),
   按弹窗确认计费方式后开通.

未开通子服务的接口调用会返回 `OperationDenied`.

## 3. 号码相关流程

### 3.1 号码申请

- 客户侧入口: 控制台 "全局号码 → 号码管理 → 申请号码".
- 接口侧: **平台未开放写 OpenAPI**, `apply_number` 类调用只能返回控制台引导.
- 申请单审核约 7 个工作日, 月租从开通日起算, 3 个月后才能注销;
  缺号会降级到所选省的省会.

### 3.2 其他号码操作

完成申请后的启停 / 改号码池 / 注销等操作: 客户在管理后台自助处理,
本 skill 提供 `toggle_number` / `update_pool` 等读写支持.

### 3.3 客户侧号码状态映射

底表 `volc_number` 有两个状态字段:

- `platform_status`: 平台状态. `1` 使用中 / `2` 平台停用 / `3` 已注销 / `4` 未使用.
- `user_status`: 用户状态. `1` 启用中 / `2` 停用中 / `3` 已注销.

对外暴露的 `numberStatusCode` (消息字段名 `numberStatus`) 由两者组合而来:

| numberStatusCode | platform_status | user_status | 含义           |
|------------------|-----------------|-------------|----------------|
| 1                | 1               | 1           | 使用中         |
| 2                | 1               | 2           | 用户侧停用     |
| 3                | 2               | 任意        | 平台停用       |
| 4                | 4               | 3           | 用户侧注销     |
| 6                | 3               | 任意        | 平台侧注销     |

> 解析号码状态时一律使用 `numberStatusCode`, 不要直接读底表两个字段.

## 4. 官方文档索引

- 隐私号产品文档: https://www.volcengine.com/docs/6358/66617
- 隐私号 API 文档: https://www.volcengine.com/docs/6358/172143
- 数据回调文档: https://www.volcengine.com/docs/6358/173360
- 火山引擎控制台 (号码申请 / 数据查询): https://console.volcengine.com/auth/login

### 4.1 CallId 常见格式

1. **隐私号 CallId**
   - 有绑定关系: `subId + "_" + providerCallId(16位 MD5)`
     例: `S17745237466453854cb2e_6255263ab1b02350`
   - 无绑定关系: `"S" + providerId(后4位) + "_" + providerCallId(16位 MD5)`
     例: `S1039_f4c432fa38d7af7b`
2. **隐私号 providerCallId**: 运营商侧生成的唯一 ID, 找运营商排查问题时必带.
3. **普通语音 SIP CallId**: 带业务前缀, 例:
   - `NM` 语音 SIP, 如 `NMBJ2026032619155628EDD7C8290511F1A8AE00163E43AF35`
   - `V`  语音通知, 如 `VZ8LFZZ2026032619155577C3080556624F53B702AECAC6`
   - `R`  智能外呼
   - `NH` 号码托管
   - `D`  双呼

> `byted-vms-cdr-record` 的 `query_cdr` 强制 `CallIdList` 参数, 没有 CallId 时不要硬调,
> 引导用户去控制台或用 `query_sip_record` 列表查.

## 5. 录音相关

1. 录音对客推送使用**带签名的公网 CDN URL**, 默认有效期 6 小时
   (URL 中 `x-expires` 字段是过期时间戳). 业务方应在过期前及时转存,
   不要把签名 URL 当永久地址存库.
2. 录音默认**主叫左声道, 被叫右声道**. 单独取一方时按声道分离.
3. 控制台 `audioRecordFlag` 录音开关只影响:
   - 对客户的录音推送
   - 客户查询接口能否查到
   - 计费
   火山侧**始终存储录音**, 管理后台一律可查 (供运营 / Oncall).
4. 录音 CDN 域名 (推送 URL host 在以下范围之一):
   - `lf6-audio-file-sign.volcvms.com`
   - `lf26-audio-file-sign.volcvms.com`
   - `lf3-audio-file-sign.volcvms.com`
   - `lf9-audio-file-sign.volcvms.com`

## 6. 数据获取注意事项

1. **优先订阅推送**, 不要轮询查询接口. 火山侧若有延迟, 查询接口可能查不到或字段
   为空. 话单 / 事件 / 录音等都建议走平台推送回调.
2. 火山以**固定出口 IP** 请求客户侧推送地址, 如果客户侧有 IP 白名单, 需将下列 IP
   全部加白:

```
220.243.131.172
220.243.131.173
101.126.59.7
101.126.59.8
101.126.59.9
123.58.10.238
123.58.10.239
```

## 7. 与本 Skill 的衔接

- 拼请求时遇到字段歧义 → 回到本 § 1~3 校对取值.
- 处理回调 / 查询返回 `numberStatus` → 用 § 3.3 表反查 (platform/user) 含义.
- 拿到的 CallId 需要给运营商或 Oncall 排查 → 见 § 4.1 + § 5 (附 CDN host 也行).
- 接到推送但客户侧 IP 拦截 → 让客户加白 § 6 列表.
