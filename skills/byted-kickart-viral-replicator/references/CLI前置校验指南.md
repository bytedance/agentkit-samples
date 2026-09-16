# KickArt CLI 前置校验指南

## 1. 适用范围

所有爆款裂变操作必须通过 `npm exec -y --package @volcengine/kickart-open-mcp@1.0.x kickart-open-cli` 执行，不得直接请求 OpenAPI。

| CLI 命令 | 用途 | 关键输出 |
| --- | --- | --- |
| `npm exec -y --package @volcengine/kickart-open-mcp@1.0.x kickart-open-cli auth_token` | 检查 OAuth 登录态并自动刷新临期 token | 当前 access token |
| `npm exec -y --package @volcengine/kickart-open-mcp@1.0.x kickart-open-cli auth_login` | 启动 OAuth 设备授权并立即返回 | 用户授权链接 |
| `npm exec -y --package @volcengine/kickart-open-mcp@1.0.x kickart-open-cli auth_complete` | 用户完成网页授权后，单次请求 token 并完成登录 | 登录及凭据保存结果 |
| `npm exec -y --package @volcengine/kickart-open-mcp@1.0.x kickart-open-cli material_pipeline_v2` | 仅用于用户明确要求独立上传或创建 KickArt 媒资 | `created.media_id`、`origin_url` |
| `npm exec -y --package @volcengine/kickart-open-mcp@1.0.x kickart-open-cli submit_viral_task_v2` | 提交爆款裂变任务 | `task_id`、`request_id`、`request_body` |
| `npm exec -y --package @volcengine/kickart-open-mcp@1.0.x kickart-open-cli query_task_v2` | 查询爆款裂变任务 | `status`、`progress`、`result_url`、`response_file_path` |

## 2. 强制前置校验

1. 执行 `command -v npm` 检查 `npm exec` 是否可用。npm 不存在时，反馈当前环境缺少 Node.js/npm 并终止操作。
2. 所有 CLI 命令固定使用 `npm exec -y --package @volcengine/kickart-open-mcp@1.0.x kickart-open-cli`，由 npm exec 获取指定版本，无需执行全局或项目级安装。
3. 执行 `npm exec -y --package @volcengine/kickart-open-mcp@1.0.x kickart-open-cli auth_token >/dev/null` 检查登录态。必须丢弃 stdout，禁止显示、记录或持久化 token。
4. npm exec 下载包或启动 CLI 失败时，反馈脱敏后的 npm 错误并终止操作，不得继续调用业务命令。
5. 登录态检查失败时执行 `npm exec -y --package @volcengine/kickart-open-mcp@1.0.x kickart-open-cli auth_login`。该命令只启动设备授权并立即返回授权链接，不会轮询授权状态。
6. 将授权链接展示给用户，引导用户在浏览器完成授权。此时必须暂停登录流程，等待用户明确确认已完成网页授权；禁止自动轮询、禁止提前执行完成命令。
7. 用户确认后，单次执行 `npm exec -y --package @volcengine/kickart-open-mcp@1.0.x kickart-open-cli auth_complete` 请求 token 并保存登录凭据。若返回授权尚未完成，告知用户继续完成网页授权并等待其再次确认，不得自动重试。
8. `auth_complete` 成功后再次执行 `npm exec -y --package @volcengine/kickart-open-mcp@1.0.x kickart-open-cli auth_token >/dev/null`；仍失败则反馈 stderr 中已脱敏的错误并终止操作。
9. 不要求用户提供长期密钥，也不主动要求用户提供 access token。只有用户明确选择导入已有 token 时，才使用：

```bash
printf '%s' "$KICKART_TOKEN" | npm exec -y --package @volcengine/kickart-open-mcp@1.0.x kickart-open-cli auth_login --with-token
```

不得把真实 token 写入命令文本、日志或对话。

### OAuth 设备授权交互

```bash
npm exec -y --package @volcengine/kickart-open-mcp@1.0.x kickart-open-cli auth_login
# 等待用户在网页完成授权并明确确认后执行
npm exec -y --package @volcengine/kickart-open-mcp@1.0.x kickart-open-cli auth_complete
```

`auth_login` 与 `auth_complete` 必须作为两个独立阶段执行。不得把两个命令连续执行，也不得使用循环反复调用 `auth_complete`。

## 3. CLI 调用规则

1. 首次使用某个业务命令或参数不确定时，先执行 `npm exec -y --package @volcengine/kickart-open-mcp@1.0.x kickart-open-cli <命令> --help`，以实际帮助为准，不猜测未声明参数。
2. 生成任务中的本地 JPEG/PNG/MP4/MOV 不调用 `material_pipeline_v2`。完成基础校验后，直接把 CLI 进程可读取的绝对路径传给 `--ref-video`、`--product-images`、`--model-images` 或 `--location-images`，由 `submit_viral_task_v2` 自动上传并转换为 URL。
3. 本地图片须校验文件存在、扩展名为 JPEG/PNG 且不超过 8MB；本地视频须校验文件存在、扩展名为 MP4/MOV 且不超过 50MB。
4. 公网 URL 可直接传给对应素材参数，无需下载或预上传。
5. 多素材参数按 CLI `--help` 声明的方式传入，保持用户提供顺序；每个路径或 URL 必须作为独立 shell 参数安全传递，不手工拼接或执行未经转义的命令字符串。
6. 只有用户明确要求“上传素材到 KickArt”“创建媒资”或“查询媒资”时，才执行 `material_pipeline_v2` 或对应分步 CLI；该独立流程不得作为生成任务的前置条件。
7. 爆款裂变使用 `submit_viral_task_v2`，默认模板为 `978755330`。
8. 提交成功后从 stdout JSON 保存 `task_id`、`request_id`、任务类型、提交时间、会话 ID 和参数摘要。
9. 查询使用 `query_task_v2`，固定传 `--source ad_variations`，默认传 `--auto-publish true`。
10. 提交后不自动轮询，仅在用户主动查询时执行查询命令。

## 4. 输出与错误处理

1. CLI 退出码为 `0` 时解析 stdout JSON；日志文本不得当作业务 JSON。
2. CLI 非零退出时读取 stderr，先移除 token 等敏感信息，再向用户说明原因和下一步操作。
3. 任务状态仅使用 `running`、`completed`、`failed`。
4. 完成时优先返回 `result_url`，同时保留 `response_file_path` 和可选的 `published_media`。
5. 禁止通过 shell 插值拼接用户输入；路径、URL、提示词等必须作为独立参数传递。
