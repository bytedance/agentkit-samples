# 群发任务

## 准备

用 `list-templates` 查询模板，可选 `--template-id`、`--signature`、`--sub-account`；
`--keyword` 可重复传入，匹配名称、正文和用途说明。结合客户用途选择模板，使用返回的 `Signature`。
`TaskFields` 声明 content 时准备任务正文，其余变量在名单中逐行填写。

按模板 `SubAccounts` 中的具体 ID 选择消息组；`All` / `*` 时用 `list-message-groups`
查询启用组，取 `subAccountId`，以 `subAccountName` 展示。已有可用选择时沿用，
只有一项时采用，多项时请客户选择。

在会话确认发送时间：未说明时问“立即发送，还是指定时间？”；已明确时沿用。
正文中的活动时间与发送时间分别处理；相对时间换成 Asia/Shanghai 的具体日期时刻并告知客户，
信息不足时补问。定时范围见 [发送契约](delivery-contracts.md)。

表单自动预检任务正文。单独检查文案用
`batch-content-check --sub-account <消息组ID> --signature <签名> --template-id <模板> --content <正文>`。

## 打开表单

`open_batch_task_creation` 传 `subAccount`、`taskName`、`signature`、`templateId`，
按 `TaskFields` 选填 `content`，并预填已确认的时间：

- 立即发送：`scheduled=false`，省略 `sendTime`。
- 定时发送：`scheduled=true`，`sendTime` 为带 `+08:00` 的 ISO 8601 时间。

保存 `flowId`，调用 `ensure_batch_task_creation_visible` 展示并等待客户操作。
无 MCP 时，以持续运行的前台任务执行并保存句柄：

    python3 -E -B <skill目录>/scripts/sms_cli.py batch-wizard \
      --sub-account <消息组ID> --task-name <名称> \
      --signature <签名> --template-id <模板> --display host

按需加 `--content <正文>`；立即发送加 `--immediate`，定时加
`--scheduled --send-time <ISO时间>`。
支持本机网页预览时，将 `QUALIFICATION_DISPLAY` 的私密 URL 交给展示工具；否则用
`--display browser`。收到 `LOCAL_FORM_STATUS {"state":"ready"}` 后告知页面就绪，
切换展示工具时复用原 URL。

客户按服务端示例上传 CSV、核对时间。页面用 `SetBatchTaskForAgent` 创建待确认任务，
展示有效号码与重复数；客户勾选确认后，以同一 `taskId` 调用 `ConsentBatchTask` 启动。
`BatchOnly=true` 仅支持群发；其他模板可在表单试发，页面按 Message ID 查询结果并支持刷新。

## 结果与取消

MCP 用 `get_batch_task_creation_result`；CLI 读取原任务最终输出。

| 结果 | 后续处理 |
| --- | --- |
| `batch_file_validated` | 保存 taskId、subAccount，告知已创建、待确认 |
| `batch_task_confirmed` | 查询任务状态；送达结果查消息日志 |
| `outcomeUnknown=true` | 按已知任务 ID 查询核实 |
| `fallbackAllowed=true` | 原流程已结束且宿主无法展示时，使用 [文件回退](batch-file-fallback.md) |

取消时先关闭表单并读取结果；有 taskId 时执行
`batch-cancel --sub-account <消息组ID> --task-id <任务>`，再用 `batch-detail` 核实状态 7。
正文或资源变更时重新准备表单；文件和时间在当前页面调整。
