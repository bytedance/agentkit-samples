# 资质表单展示

按宿主当前提供的工具选择展示方式，不根据产品名猜测：

1. 存在 `open_qualification_application` 时先调用它，取得 `flowId` 后立即调用一次
   `ensure_qualification_application_visible`。返回 `opened` 即等待客户填写；返回
   `not_opened` 时先调用 `cancel_qualification_application`，再进入下一步。
2. 宿主提供能打开本机 URL 的内置浏览器或网页预览工具时，在持续运行的前台任务中执行
   `qualification-wizard --display host`，从 `QUALIFICATION_DISPLAY` 读取私密 URL 并
   原样交给该工具。
3. 宿主没有内置网页能力时，执行 `qualification-wizard --display browser`，由系统默认
   浏览器打开表单。

内置浏览器打开失败时，用系统浏览器打开同一私密 URL，不要启动第二个向导。任一时刻只
保留一个向导进程，并持续读取其输出直到完成、放弃或报错。

## 执行边界

- MCP App 正常时只在右侧面板展示；`ensure_qualification_application_visible` 只确认
  页面首次心跳，不自行打开浏览器。
- 没有 MCP App 工具时直接选择第 2 或第 3 种方式，不让普通客户配置 MCP。
- 不使用 `show_widget` 承担材料上传或最终提交。
- 不让客户选择展示方式、执行命令或复制 URL；私密 URL 不写入对话或最终回复。
- 客户取消任务时关闭当前 flow 或前台任务，不遗留本机服务。

## 排障

`open_qualification_application` 返回错误时先按错误码处理，不把业务失败误判成展示失败。
返回成功但 `ensure_qualification_application_visible` 报告 `not_opened` 时，按上述顺序降级，
不再调用 MCP App。

需要定位 MCP App 时读取 `QUALIFICATION_MCP_APP` 和 `QUALIFICATION_DISPLAY_EVENT`：

- 有 `flow_ready`、无 `resource_read`：宿主没有读取 UI Resource；
- 有 `resource_read`、无 `wizard_document_requested`：宿主没有加载本机表单；
- 有 `wizard_document_requested`、无 `display_ready`：页面已请求，但前端没有开始心跳。

这些事件不得包含私密 URL、访问 token 或表单数据。
