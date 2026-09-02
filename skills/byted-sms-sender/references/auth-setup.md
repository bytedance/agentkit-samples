# 鉴权准备

只在首次调用或鉴权失败时读取。普通客户只操作浏览器；其余由 Agent 完成。

先运行：

```bash
python3 -B <skill目录>/scripts/sms_cli.py auth-doctor
```

`error.remediation` 是唯一下一步，保留其 `argv`、`env`、`target`、
`continue_with_env` 和 `cleanup`：

- `install_ve`：有 npm 就安装官方 npm 包；否则下载匹配系统和架构的官方 Release，
  校验 SHA-256 后安装到用户可写路径。不要要求客户安装 Node/npm。
- `run_login`：执行顶层 `argv`，不要改成裸 `ve login`；保留返回的 job/session。
- `wait_for_customer_browser_login`：等待客户回复，再执行 `after_customer_ready`。
- `run_auth_doctor`、`run_command`、`configure_environment`：原样执行并继续原任务。
- 没有 remediation 或系统临时目录不可用时停止，不给客户命令或多套方案。

同一时间只允许一个登录会话。异步执行时持续读取同一 job/session 的最终 JSON，不设
短登录超时；内置登录进程使用 30 分钟安全上限。`auth_ready` 前不处理业务；成功后自动恢复原任务。非结构化错误只补跑一次
`auth-doctor`，未复诊前不启动第二个登录。

## 网页授权选择

执行 `run_login.argv` 后立即读取 `customer_interaction.selection`：

1. 先执行 `current_login_watch` 非阻塞检查同一登录 job；已返回 `auth_ready` 时不展示
   选择框，直接恢复原任务。
2. 只有 job 仍在等待时才使用当前平台的结构化选择工具；没有时才输出 remediation 的
   fallback 文案。
3. 原样使用 remediation 的标题、问题、选项和说明，不在提示前后添加长段解释。
4. 选择框显示期间继续执行同一个 watch；一旦 `auth_ready`，立即关闭选择框并恢复原任务。
5. 账号密码登录时等待当前 job；其他登录方式未成功才进入下节。

## 其他方式登录

原样展示 remediation 的其他登录提示。等待期间不 cleanup，并持续观察当前 job；客户
回复后再检查一次，尚未成功才执行 `after_customer_ready`。该动作负责终止旧登录并
复用目标、Profile、环境和 cleanup 上下文重启普通授权。只允许重启一次；仍失败或客户
放弃时终止登录、cleanup 并停止。不索取登录入口链接、不执行 `ve configure sso`，也不
改走 AK/SK。

## 远程回退

只有确认 loopback 不可用时才执行 `run_login.fallback.argv`。Agent 必须能读取授权结果
页并写回同一会话；否则停止。不得让客户提供授权码或操作终端，不得后台化、另起登录
进程、解析 code/state，或将授权响应写入命令、环境变量、文件和日志。

## 客户明确选择 AK/SK

只有客户主动选择 AK/SK 时，才提示客户在本机配置
`VOLCENGINE_ACCESS_KEY` 和 `VOLCENGINE_SECRET_KEY`；临时凭证再配置
`VOLCENGINE_SESSION_TOKEN`。需要复用时可将同一组变量写入本机
`~/.openclaw/.env`。不得把凭证发到对话或放入命令参数；切换前执行待处理 cleanup。

## 临时目录

所有 `ve` 子进程使用系统临时目录下的 Skill 私有目录；Windows 同步登录环境。
不得使用用户主目录、仓库或固定 `/tmp/ve-home`，不得修改 `~/.volcengine`。清理只
执行 remediation 给出的 `auth-cleanup`，不手写删除。Agent 不读取配置和缓存；内置
脚本只在私有临时目录内解析当前登录凭证。
