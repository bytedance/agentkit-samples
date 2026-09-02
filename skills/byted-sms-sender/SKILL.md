---
name: byted-sms-sender
metadata:
  author: volcengine-sms-team
  version: 1.4.0
description: 使用火山引擎发送和管理国内短信（Volcengine SMS）。用户想发短信、群发短信、发送验证码、通知短信或营销短信，或者需要开通短信服务、查询或创建资质、上传并识别营业证件、填写经办人、责任人或法人材料、申请签名和模板、查询发送记录、回执、送达率、成功率与失败原因时使用。支持服务开通引导、本机资质申请向导、消息组与资质查询、签名和模板申请、单发、群发、回执与客户可见的数据分析。资质敏感材料只通过本机私密表单处理；不要在对话中收集，或者代替客户同意服务协议、处理国际短信、WhatsApp 和非客户可见的技术诊断。
---

# 火山引擎短信

始终通过 `python3 -B <skill目录>/scripts/sms_cli.py` 执行业务，不绕过脚本调用写
Action。默认客户不会使用终端：Agent 负责安装、登录、命令和清理，客户只操作浏览器
并确认业务写入。除非客户询问，不展示命令、JSON、CLI、Profile、HOME、AK/SK 或沙箱。

## 入口流程

1. 首次调用或鉴权失败时读取 [auth-setup.md](references/auth-setup.md)，执行
   `auth-doctor` 并严格跟随唯一 `error.remediation`；`auth_ready` 后恢复原任务。
2. 首次业务调用执行只读 `list-message-groups`。只有 `RE:0001` 才读取
   [service-onboarding.md](references/service-onboarding.md)；空列表和资源缺失不代表服务
   未开通。
3. 按任务读取下面最小参考集合，再执行 CLI。

## 按任务读取

- 所有任务先读公共 Action 配置与错误规则：[actions.md](references/actions.md)。
- 资质、签名、模板申请读
  [application-contracts.md](references/application-contracts.md)。
- 资质材料和本机表单再读
  [qualification-materials.md](references/qualification-materials.md)；展示方式由其中链接的
  `qualification-display.md` 决定。
- 单发、群发、回执和分析读
  [delivery-contracts.md](references/delivery-contracts.md)。
- 需要完整编排顺序时读 [workflows.md](references/workflows.md)。
- 写操作授权、脱敏、重试和对账统一读 [rules.md](references/rules.md)。

## CLI 工作流

- 查询：`list-message-groups`、`message-group-detail`、`list-qualifications`、
  `list-signatures`、`list-templates`。
- 资质：先尝试 MCP App 右侧面板；调用 `open_qualification_application` 后紧接着调用
  `ensure_qualification_application_visible`。面板不可见时按
  [qualification-display.md](references/qualification-display.md) 改用宿主内置浏览器，
  宿主不支持时才使用系统浏览器。
- 申请：`*-preview` → 客户确认 → `*-submit`。
- 单发：`match-template` → `send-preview` → 客户授权 → `send-submit` →
  `send-status`。
- 群发：`batch-template-demo` / `batch-precheck` → `batch-create` →
  `batch-launch-preview` → 指定任务授权 → `batch-launch-submit`；管理使用
  `batch-detail`、`batch-list`、`batch-cancel`。
- 分析：`analytics`；只有需要消息级证据时增加 `--include-logs`。

## 不可变边界

- 鉴权只执行 remediation；同一时间一个登录会话。其他登录方式不索取登录入口链接，AK/SK
  只在客户主动选择时提示一套 `VOLCENGINE_*` 变量。
- 资质敏感材料只在本机向导填写。Agent 读取掩码后的 `QUALIFICATION_EXCHANGE` 和
  `QUALIFICATION_FAILURE` 排查，不要求客户复制字段或上传到对话。
- 申请、发送和任务启动都基于当前预览授权；字段变化后重新预览。
- 可能已发出的写请求不重试、不切换调用路径，返回 `outcome_unknown` 并按契约对账。
- 创建或启动群发不代表送达；只有公开发送日志是消息级证据。
- 最终输出不包含完整个人信息、图片、文件地址、凭证、ticket、Authorization 或签名
  URL 查询参数；保留公开 Request ID 和错误码，不推断内部原因。
