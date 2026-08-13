---
name: byted-sms-sender
version: 1.3.1
metadata:
  author: volcengine-sms-team
description: 火山引擎国内短信（SMS）与短信营销全流程服务，面向外部客户提供短信开通后的运营、发送和分析能力。用户只要提到“短信”“短信服务”“短信营销”“营销短信”“短信群发”“群发短信”“批量短信”“验证码短信”“通知短信”“短信签名”“短信模板”“短信发送”“群发任务”“发送记录”“短信回执”“送达率”“成功率”“失败原因”或“短信数据分析”，或者希望通过火山引擎发送、管理、查询、排查和分析国内短信时，应优先使用。支持已审核资质和消息组查询、签名与模板申请、单条短信发送与回执查询、群发任务创建与明确授权后的启动、任务取消，以及客户可见的数据分析。不要用于资质申请、国际短信、WhatsApp 或非客户可见的技术诊断。
---

# 火山引擎短信

先定位本 Skill 目录，再将
`python3 <skill目录>/scripts/sms_cli.py` 作为唯一命令入口。
脚本可从任意当前目录运行。脚本优先通过 `ve volcsms` 执行 Action，并继续负责
预检、授权摘要、脱敏与对账；不要绕过脚本直接执行写 Action。不要手写 HTTP 请求
或臆造 Action 名，构造不熟悉的参数前先查看对应命令的 `--help`。

## 鉴权边界

- 对短信 API 的请求只使用火山引擎 V4 AK/SK 鉴权；临时凭证同时签入
  SessionToken。
- 第一优先级：使用 `ve >= 1.1.0` 的 `ve volcsms <Action>` 命令。由官方 CLI
  复用 `ve login`、当前 Profile 或 `VOLCENGINE_PROFILE` 指定的 Profile，并
  负责凭证刷新、签名与请求发送。Skill 不读取 CLI 配置文件。
- 第二优先级：只有 CLI 不存在、不支持 `volcsms`，或在请求发出前明确无法使用
  时，才使用兼容直连路径。该路径先通过官方 `CLIConfigCredentialProvider`
  复用 `ve` Profile；无法解析时按顺序读取进程环境变量和
  `~/.openclaw/.env` 中完整的 `VOLCENGINE_ACCESS_KEY` 与
  `VOLCENGINE_SECRET_KEY`。临时凭证同时使用 `VOLCENGINE_SESSION_TOKEN`。
- 兼容直连路径内，任一凭证来源或变量组不完整时直接报错，不跨来源或跨变量组
  拼接。没有可用凭证时，只提示配置 `VOLCENGINE_ACCESS_KEY`、
  `VOLCENGINE_SECRET_KEY`，以及临时凭证所需的 `VOLCENGINE_SESSION_TOKEN`。
- 如果 `ve` 不存在或低于 `1.1.0`，先通过官方 npm 包
  `@volcengine/cli` 安装或升级。`requirements.txt` 中的 Python SDK 只用于
  兼容直连路径；不要自行读取 CLI 配置文件。
- 不要直接读取或解析 Volcengine CLI 配置、SSO 缓存或控制台登录缓存；
  凭证加载与刷新必须交给官方 CLI 或 Provider。
- 不要通过命令行参数传递 AK/SK 或 SessionToken。
- 官方 Provider 返回的 Session Token 属于客户直连 V4 凭证，必须作为已签名的
  `X-Security-Token` 发送。
- 调用身份由最终选中的鉴权路径确定，不接受账号 ID 覆盖。

## 选择工作流

- 查询 Action 名、参数、版本、响应字段和重试分类时，读取
  [references/actions.md](references/actions.md)。
- 申请签名或模板、发送短信、管理群发任务前，读取
  [references/workflows.md](references/workflows.md)。
- 执行任何写操作或处理客户数据前，读取
  [references/rules.md](references/rules.md)。

## 命令导航

- 资源查询：`list-message-groups`、`message-group-detail`、
  `list-qualifications`、`list-signatures`、`list-templates`。
- 申请：先执行 `signature-preview`，再执行 `signature-submit`；
  先执行 `template-preview`，再执行 `template-submit`。
- 单条发送：使用完整客户短信内容、签名、消息组和短信类型调用
  `match-template`，查找内容完全一致且已审核通过的模板。随后用明确选定的模板
  ID 执行 `send-preview`，取得当前会话中的明确授权后执行 `send-submit`；
  使用 `send-status` 查询回执。
- 群发：`batch-template-demo`、`batch-precheck`、`batch-create`、
  `batch-detail`、`batch-list`、`batch-launch-preview`、
  `batch-launch-submit`、`batch-cancel`。
- 客户数据分析：使用 `analytics`。聚合统计是提交级数据；只有显式传入
  `--include-logs` 才查询消息级证据。分析账号全量发送日志时，先枚举客户可见的
  消息组，再逐个查询。`--channel-type` 只限定聚合统计；
  `--mobile` 只作为发送日志请求过滤条件，必须与 `--include-logs` 同时使用，
  不得返回，也不会限定同一报告中的聚合趋势。

## 强制安全门禁

- 不支持资质申请，只查询已审核资质。如果客户没有可用资质，停止签名申请流程，
  明确引导客户登录火山引擎控制台，在“国内短信 > 资质管理”完成资质申请；待资质
  审核通过后再继续。不要代替客户提交资质申请。
- 签名和模板申请必须先生成预览；只有执行摘要仍与预览一致时才能提交。
- 签名申请必须遵循客户明确指定的消息组子集。客户不确定或未指定时，绑定当前
  可见的全部消息组。默认全选时，提交前立即重新查询；可见集合变化后必须重新
  生成预览。
- 签名来源 `source` 必须为整数：`1 = 公司`、`2 = App`、
  `3 = 商标`。消息组行业不是签名申请门禁；只有客户主动询问时才使用
  `message-group-detail`。
- 单条发送必须针对当前脱敏发送摘要取得明确授权。只有取得授权后，才能把预览
  摘要作为授权摘要传入；泛化的“继续”或“是”不构成授权。
- 单条发送前，根据完整短信内容判断短信类型，再匹配模板。只检查本次发送需要的
  消息组、签名、模板及变量关系；不要查询资质或消息组行业。签名缺少
  `usable`、资质 ID 或短信类型字段不视为失败，但明确
  `usable=false` 必须拒绝。
- 按客户明确的发送方式选择单条发送或群发；客户明确要求群发时，即使本次只有一个
  测试号码也使用群发工作流。
- 创建群发任务不等于授权发送。展示最新任务摘要并在当前会话收到
  `确认启动任务 <taskId>` 后，才能启动。
- 保留群发创建交接信息：`taskId`、`subAccount`、文件 SHA-256 和号码统计。
  任务详情缺少这些值时，在启动预览中补入交接信息。
- 发送或启动前立即重新查询可变资源；任何摘要变化都会使原授权失效。
- 群发任务禁止使用验证码模板。
- 群发任务状态 `3`、`4`、`5` 只表示已接受启动、正在准备或正在发送；不能据此
  宣称任务完成、短信已送达或发送成功。状态 `6` 只表示任务处理完成，也不能替代
  消息级回执。只有公开发送日志提供送达证据时，才能报告具体号码成功或失败；暂时
  查不到数据时说明“已启动，回执待更新”，不要把零统计或查询失败解释成成功。
- 保留公开短信错误码，只能通过 `actions.md` 中的官方文档链接解释；
  不要硬编码、推断或输出非公开实现原因。
- 除非 `actions.md` 明确声明服务端幂等字段与对账方式，否则不要自动重试写
  Action。
- CLI 写调用只有在能够确认子进程未发出请求时才允许进入兼容路径。CLI 超时、
  响应丢失或无法判断是否已发送时，必须返回 `outcome_unknown`，不得换后端重放。
- 如果写请求可能已到达服务端但响应丢失，返回 `outcome_unknown`，并使用查询
  Action 对账；不要盲目重复提交。

## 输出边界

返回 CLI JSON 信封，但不要暴露完整手机号、可能含敏感信息的短信内容、凭证、
Authorization 请求头、签名 URL 查询参数，以及任何非客户可见字段。
保留公开 Request ID 与公开错误码，供客户支持排查。
