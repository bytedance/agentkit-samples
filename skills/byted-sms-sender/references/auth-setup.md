# 鉴权准备

业务命令返回鉴权错误或登录指引时读取。客户在浏览器完成授权，Agent 执行登录并读取结果。
需要诊断时运行：

```bash
python3 -E -B <skill目录>/scripts/sms_cli.py auth-doctor
```

按 `error.remediation` 的 `argv`、`env`、`target`、`continue_with_env` 和 `cleanup` 执行：

- `install_ve`：从返回的官方来源安装到用户可写路径；Release 文件用同一版本的校验文件核验 SHA-256。
- `run_login`：执行顶层 `argv`，保存平台受管的 job/session；脚本按 CLI 能力选择登录流程。
  本地回调流程由 CLI 打开网页并接收授权结果。回调不可用时，结束旧登录，沿用其环境与
  执行位置运行 `fallback.argv`（`--remote`）。远程任务以交互模式启动（如执行工具的
  `tty: true`），保持标准输入可写，将授权响应写回同一个等待中的登录进程。
  设备码流程由脚本关闭自动开页，Agent 优先使用本次进程返回的预填码链接；需要手动
  填码时，先向客户展示设备码和授权链接，再打开页面。
  持续读取当前登录任务；最终 JSON 为 `auth_ready` 后恢复原业务任务。
- `run_auth_doctor`、`run_command`、`configure_environment`：原样执行并继续原任务。

当前登录会话贯穿授权和诊断。非结构化错误补跑一次 `auth-doctor`；取消时终止当前任务，
再执行返回的 cleanup。缺少 remediation 或临时目录不可用时，保留错误并说明阻塞。

## 环境与凭证

安装包固定登录、短信和上传环境；`runtime-info` 可查看环境和控制台地址。
更换环境时安装对应 ZIP。网页登录续期保持同一会话的预览；账号、IAM 身份或登录会话
改变后重新准备预览。

脚本将 `ve` 凭据保存在按环境隔离的系统临时目录，清理由 `auth-cleanup` 完成。
账号、密码和短信验证码由客户在官方页面输入。
客户主动选择 AK/SK 时，在本机配置当前环境的 `VOLCENGINE_ACCESS_KEY`、
`VOLCENGINE_SECRET_KEY`；临时凭证再配置 `VOLCENGINE_SESSION_TOKEN`。
需复用时可写入本机 `~/.openclaw/.env`，对话只确认配置是否就绪。
