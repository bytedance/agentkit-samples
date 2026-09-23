---
name: byted-sms-sender
license: Apache-2.0
metadata:
  author: volcengine-sms-team
  version: 1.4.5
description: 火山引擎国内短信服务（Volcengine SMS）。支持资质、签名和模板的申请与查询，单条、群发和定时发送，以及发送记录、回执、统计查询与失败排查。
---

# 火山引擎短信

提供国内短信的资质、签名和模板申请与查询，单条与群发发送，以及发送记录、回执和统计分析。
Agent 按客户目标选择所需能力，负责工具调用、资源查询和参数填写，向客户说明业务选择与结果。

查询使用 `execute_sms_read_action(action, params)`，传接口原生参数；预览和已确认的写操作
使用相应 read/write 工具的 `argv`。无 MCP 时运行
`python3 -E -B <skill目录>/scripts/sms_cli.py`，原生查询为
`api-read --action <Action> --params '<JSON>'`。环境由安装包固定，参数可查 `--help`。

资质材料、号码名单和凭据留在私密表单及本机，对话展示摘要。
查询保留业务字段和审核维度，由 Agent 按客户问题解释；写操作按当前预览确认，结果未知时先查询核实。

按任务读取：

| 任务 | 参考 |
| --- | --- |
| 查询资质、消息组、签名及审核状态，申请签名或模板 | [application-contracts.md](references/application-contracts.md) |
| 新建或补充资质、上传证件 | [qualification-materials.md](references/qualification-materials.md) |
| 模板查询、单条发送、发送记录、统计 | [delivery-contracts.md](references/delivery-contracts.md) |
| 群发准备、表单与任务结果 | [batch-form.md](references/batch-form.md) |
| 组合任务 | [workflows.md](references/workflows.md) |
| 鉴权错误或提示登录 | [auth-setup.md](references/auth-setup.md) |
| 返回 `RE:0001` | [service-onboarding.md](references/service-onboarding.md) |
| 写操作授权、结果未知 | [rules.md](references/rules.md) |
| 接口与错误码 | [actions.md](references/actions.md) |
