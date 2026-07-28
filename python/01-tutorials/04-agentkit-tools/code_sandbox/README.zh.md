# Code Sandbox Session

本示例包含两个脚本：

- `ensure_session.py`：确保指定 `tool-id` 和 `session-id` 对应的 AgentKit sandbox session 可用。
- `codex_ws_tui.py`：通过终端 TUI 连接 Codex app-server，并与 Codex 对话。

`ensure_session.py` 的处理顺序：

1. 查询指定 `session-id` 对应的远端 session 是否存在。
2. 如果 session 不存在，查询该 `session-id` 是否存在快照。
3. 如果存在快照，使用最新快照恢复 session。
4. 如果不存在快照，创建新的 session。

## 前置条件

安装 AgentKit Python SDK：

```bash
pip install agentkit-sdk-python==0.8.0
```

也可以在当前目录通过 `requirements.txt` 安装：

```bash
pip install -r requirements.txt
```

运行 `ensure_session.py` 前需要配置火山引擎凭证：

```bash
export VOLCENGINE_ACCESS_KEY=<your_access_key>
export VOLCENGINE_SECRET_KEY=<your_secret_key>
export VOLCENGINE_REGION=<your_region>
```

## 使用方法

### 确保 Sandbox Session 可用

使用命名参数：

```bash
python3 ensure_session.py \
  --tool-id <tool-id> \
  --session-id <session-id>
```

使用位置参数：

```bash
python3 ensure_session.py <tool-id> <session-id>
```

从仓库根目录运行：

```bash
python3 python/01-tutorials/04-agentkit-tools/code_sandbox/ensure_session.py \
  --tool-id <tool-id> \
  --session-id <session-id>
```

### 连接 Codex App-Server

传入 AgentKit sandbox endpoint。脚本会自动将其转换成 Codex app-server WebSocket URL：

```bash
python3 codex_ws_tui.py \
  --url 'https://<sandbox-host>/?faasInstanceName=<instance>&Authorization=<token>'
```

例如输入：

```bash
https://example.com/?faasInstanceName=demo-sandbox&Authorization=secret
```

实际连接地址会转换为：

```bash
wss://example.com/v1/codex/app-server/?faasInstanceName=demo-sandbox&Authorization=secret
```

进入交互模式：

```bash
python3 codex_ws_tui.py \
  --url 'https://<sandbox-host>/?faasInstanceName=<instance>&Authorization=<token>'
```

发送单条消息并退出：

```bash
python3 codex_ws_tui.py \
  --url 'https://<sandbox-host>/?faasInstanceName=<instance>&Authorization=<token>' \
  --message '你是谁？'
```

恢复已有 Codex thread：

```bash
python3 codex_ws_tui.py \
  --url 'https://<sandbox-host>/?faasInstanceName=<instance>&Authorization=<token>' \
  --thread-id <thread-id>
```

如果需要额外请求头：

```bash
python3 codex_ws_tui.py \
  --url 'https://<sandbox-host>/?faasInstanceName=<instance>&Authorization=<token>' \
  --header 'X-Workspace-Id: <workspace-id>'
```

TUI 内置命令：

```text
/new      创建新的 Codex thread。
/thread   打印当前 thread ID。
/help     显示帮助命令。
/exit     关闭客户端。
/quit     关闭客户端。
```

## 参数说明

`ensure_session.py`：

```text
--tool-id               AgentKit sandbox tool ID。
--session-id            需要确保可用的用户 session ID。
--ttl                   Session TTL，单位秒。默认值：28800。
--region                火山引擎地域。默认读取 VOLCENGINE_REGION 或 SDK 配置。
--access-key            火山引擎 Access Key。默认读取 VOLCENGINE_ACCESS_KEY。
--secret-key            火山引擎 Secret Key。默认读取 VOLCENGINE_SECRET_KEY。
--session-token         STS 临时凭证 token。默认读取 VOLCENGINE_SESSION_TOKEN。
--snapshot-page-size    查询快照时的分页大小。默认值：100。
--no-tos-mount-points   创建新 session 时不从 tool 复制 TOS mount points。
```

`codex_ws_tui.py`：

```text
--url                   Sandbox endpoint 或 Codex app-server WebSocket URL。
                        默认读取 CODEX_WS_URL。
--message               发送单条消息，输出 Codex 纯文本回复后退出。
--thread-id             恢复已有 Codex thread。默认读取 CODEX_THREAD_ID。
--cwd                   thread/start 或 thread/resume 使用的工作目录。
--model                 thread/start 或 thread/resume 使用的模型。
--token                 可选 Bearer token 请求头。默认读取 CODEX_WS_TOKEN。
--header                额外请求头，格式为 'Name: Value'，可重复传入。
--multiline             交互模式下启用多行输入。
--timeout               请求和 turn 超时时间，单位秒。默认值：300。
--ping-interval         WebSocket ping 间隔，单位秒。默认值：20。
--ping-timeout          WebSocket ping 超时时间，单位秒。默认值：20。
--verbose               将 JSON-RPC 方法发送和接收事件打印到 stderr。
```

## 示例

### 确保 Sandbox Session 可用

使用默认 TTL：

```bash
python3 ensure_session.py \
  --tool-id tl-xxxxxxxx \
  --session-id demo-session
```

使用自定义 TTL：

```bash
python3 ensure_session.py \
  --tool-id tl-xxxxxxxx \
  --session-id demo-session \
  --ttl 3600
```

创建新 session 时跳过 TOS mount point 设置：

```bash
python3 ensure_session.py \
  --tool-id tl-xxxxxxxx \
  --session-id demo-session \
  --no-tos-mount-points
```

### Codex WebSocket TUI

使用环境变量：

```bash
export CODEX_WS_URL='https://<sandbox-host>/?faasInstanceName=<instance>&Authorization=<token>'
export CODEX_THREAD_ID=<thread-id>

python3 codex_ws_tui.py
```

单条消息模式：

```bash
python3 codex_ws_tui.py \
  --url 'https://<sandbox-host>/?faasInstanceName=<instance>&Authorization=<token>' \
  --message '总结一下这个工作区'
```

## 输出说明

`ensure_session.py` 输出 JSON。`action` 字段表示实际执行的动作：

- `existing`：找到已有 session。
- `restored_from_snapshot`：使用最新快照恢复 session。
- `created`：创建了新的 session。

示例：

```json
{
  "action": "restored_from_snapshot",
  "tool_id": "tl-xxxxxxxx",
  "session_id": "demo-session",
  "instance_id": "ss-xxxxxxxx",
  "endpoint": "https://example.endpoint",
  "snapshot_id": "snap-xxxxxxxx"
}
```

`codex_ws_tui.py --message` 输出 Codex 的纯文本回复；交互模式会在终端中持续显示对话内容。
