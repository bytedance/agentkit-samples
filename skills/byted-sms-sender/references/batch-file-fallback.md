# 表单不可用时的文件回退

仅在宿主无法展示群发表单、原表单已关闭且返回 `fallbackAllowed=true` 时读取本文。
正常群发入口见 [batch-form.md](batch-form.md)。

在此回退流程中取得客户提供的本机 CSV 文件路径，由脚本直接读取文件。
使用 `batch-template-demo` → `batch-precheck` → `batch-create` →
`batch-launch-preview` → 客户确认 → `batch-launch-submit`。
创建按 TaskFields 选填 content；启动授权为 `确认启动任务 <taskId>`。
详细字段及状态见 [delivery-contracts.md](delivery-contracts.md)，结果未知见 [rules.md](rules.md)。

`batch-template-demo` 与 `batch-precheck` 均填写 `--sub-account`、`--template-id`，
`batch-precheck` 另填 `--file`。脚本调用现有名单示例接口，按返回表头校验文件。
创建时使用客户已确认的签名、模板、消息组和文件内容。
