# 资质表单展示

按宿主提供的工具选择入口，Agent 负责展示，客户在页面填写材料。

## MCP 表单

调用 `open_qualification_application` 保存 `flowId`，再调用
`ensure_qualification_application_visible`；`opened` 表示页面已发出首次心跳。
返回 `not_opened` 时，用 `open_qualification_application_in_browser` 打开同一个 flow；
宿主提供本机网页预览但缺少该工具时，取消当前 MCP flow，改用下面的 CLI 入口。

## CLI 表单

在持续运行的前台任务中执行 `qualification-wizard --display host`，保存任务句柄。
从 `QUALIFICATION_DISPLAY` 读取私密 URL，原样交给宿主的本机网页展示工具。
仅支持系统浏览器的宿主使用 `--display browser`。切换展示工具时复用同一私密 URL，
保留同一份草稿。

`LOCAL_FORM_STATUS {"state":"ready"}` 表示前端已运行并发出心跳，此时告知客户页面已就绪。
任务运行中持续读取原句柄，最终结果表示提交、放弃或错误。客户取消时关闭当前 flow
或前台任务，释放本机服务。

## 排障

业务错误按错误码处理；展示状态用于选择上述展示入口。诊断事件含义：

| 事件 | 含义 |
| --- | --- |
| `flow_ready` | MCP 已创建本机服务 |
| `resource_read` | 宿主已读取 UI Resource |
| `wizard_document_requested` | 浏览器已请求页面文档 |
| `display_ready` / CLI `LOCAL_FORM_STATUS` | 前端已开始心跳 |

私密 URL 与访问 token 仅在展示工具中使用；对话和诊断摘要使用状态及错误标识。
