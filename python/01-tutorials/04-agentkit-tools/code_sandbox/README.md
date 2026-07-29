# Code Sandbox Session

This example provides a helper script to ensure an AgentKit sandbox session is
available for a given `tool-id` and `session-id`.

It also includes a terminal WebSocket client for talking to Codex from a TUI.

The script follows this order:

1. Query whether a remote session exists for the provided `session-id`.
2. If no session exists, query session snapshots for the `session-id`.
3. If snapshots exist, restore the latest snapshot.
4. If no snapshot exists, create a new session.

## Prerequisites

Install the AgentKit Python SDK:

```bash
pip install agentkit-sdk-python==0.8.0
```

Or install from the requirements file in this directory:

```bash
pip install -r requirements.txt
```

Configure Volcano Engine credentials before running:

```bash
export VOLCENGINE_ACCESS_KEY=<your_access_key>
export VOLCENGINE_SECRET_KEY=<your_secret_key>
export VOLCENGINE_REGION=<your_region>
```


## Usage

### Ensure Sandbox Session

Run with named arguments:

```bash
python3 ensure_session.py \
  --tool-id <tool-id> \
  --session-id <session-id>
```

Run with positional arguments:

```bash
python3 ensure_session.py <tool-id> <session-id>
```

Run from the repository root:

```bash
python3 python/01-tutorials/04-agentkit-tools/code_sandbox/ensure_session.py \
  --tool-id <tool-id> \
  --session-id <session-id>
```

### Connect Codex App-Server

Pass the AgentKit sandbox endpoint. The script automatically converts it to the
Codex app-server WebSocket URL:

```bash
python3 codex_ws_tui.py \
  --url 'https://<sandbox-host>/?faasInstanceName=<instance>&Authorization=<token>'
```

For example, this input:

```bash
https://example.com/?faasInstanceName=demo-sandbox&Authorization=secret
```

is connected as:

```bash
wss://example.com/v1/codex/app-server/?faasInstanceName=demo-sandbox&Authorization=secret
```

Start interactive mode:

```bash
python3 codex_ws_tui.py \
  --url 'https://<sandbox-host>/?faasInstanceName=<instance>&Authorization=<token>'
```

Send a single message and exit:

```bash
python3 codex_ws_tui.py \
  --url 'https://<sandbox-host>/?faasInstanceName=<instance>&Authorization=<token>' \
  --message '你是谁？'
```

Resume an existing Codex thread:

```bash
python3 codex_ws_tui.py \
  --url 'https://<sandbox-host>/?faasInstanceName=<instance>&Authorization=<token>' \
  --thread-id <thread-id>
```

If the endpoint requires extra request headers:

```bash
python3 codex_ws_tui.py \
  --url 'https://<sandbox-host>/?faasInstanceName=<instance>&Authorization=<token>' \
  --header 'X-Workspace-Id: <workspace-id>'
```

TUI commands:

```text
/new      Create a new Codex thread.
/thread   Print the current thread ID.
/help     Show commands.
/exit     Close the client.
/quit     Close the client.
```

## Options

`ensure_session.py`:

```text
--tool-id               AgentKit sandbox tool ID.
--session-id            User session ID to ensure.
--ttl                   Session TTL in seconds. Default: 28800.
--region                Volcano Engine region. Defaults to VOLCENGINE_REGION.
--access-key            Access key. Defaults to VOLCENGINE_ACCESS_KEY.
--secret-key            Secret key. Defaults to VOLCENGINE_SECRET_KEY.
--session-token         STS session token. Defaults to VOLCENGINE_SESSION_TOKEN.
--snapshot-page-size    Page size when listing snapshots. Default: 100.
--no-tos-mount-points   Do not copy TOS mount points from the tool when creating
                        a new session.
```

`codex_ws_tui.py`:

```text
--url                   Sandbox endpoint or Codex app-server WebSocket URL.
                        Defaults to CODEX_WS_URL.
--message               Send one message, print the plain-text response, then exit.
--thread-id             Resume an existing Codex thread. Defaults to CODEX_THREAD_ID.
--cwd                   Optional working directory for thread/start or thread/resume.
--model                 Optional model for thread/start or thread/resume.
--token                 Optional bearer token header. Defaults to CODEX_WS_TOKEN.
--header                Extra request header in 'Name: Value' format.
--multiline             Enable multiline prompt input.
--timeout               Request and turn timeout in seconds. Default: 300.
--ping-interval         WebSocket ping interval in seconds. Default: 20.
--ping-timeout          WebSocket ping timeout in seconds. Default: 20.
--verbose               Print JSON-RPC method send/receive events to stderr.
```

## Examples

### Ensure Sandbox Session

Use the default TTL:

```bash
python3 ensure_session.py \
  --tool-id tl-xxxxxxxx \
  --session-id demo-session
```

Use a custom TTL:

```bash
python3 ensure_session.py \
  --tool-id tl-xxxxxxxx \
  --session-id demo-session \
  --ttl 3600
```

Skip TOS mount point setup when creating a new session:

```bash
python3 ensure_session.py \
  --tool-id tl-xxxxxxxx \
  --session-id demo-session \
  --no-tos-mount-points
```

### Codex WebSocket TUI

Use environment variables:

```bash
export CODEX_WS_URL='https://<sandbox-host>/?faasInstanceName=<instance>&Authorization=<token>'
export CODEX_THREAD_ID=<thread-id>

python3 codex_ws_tui.py
```

One-shot message:

```bash
python3 codex_ws_tui.py \
  --url 'https://<sandbox-host>/?faasInstanceName=<instance>&Authorization=<token>' \
  --message '总结一下这个工作区'
```

## Output

`ensure_session.py` prints JSON. The `action` field indicates what happened:

- `existing`: an existing session was found.
- `restored_from_snapshot`: the latest snapshot was restored.
- `created`: a new session was created.

Example:

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
