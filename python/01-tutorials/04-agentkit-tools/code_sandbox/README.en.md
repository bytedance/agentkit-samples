# Code Sandbox Session

This example provides four scripts:

- `ensure_session.py`: Ensures an AgentKit sandbox session is available for a given `tool-id` and `session-id`.
- `codex_ws_tui.py`: A terminal WebSocket TUI client that connects to the Codex app-server and chats with Codex.
- `list_snapshots.py`: Lists all session snapshots for a given AgentKit sandbox tool. Supports filtering by UserSessionId, SessionId, and creation time range. Automatically paginates through all results.
- `restore_from_snapshot.py`: Restores an AgentKit sandbox session from a given `tool-id` and `snapshot-id`, printing the recovered session details (endpoint, status, TTL, etc.).

For a full local workbench that manages AgentKit Tools and Sessions and opens
Codex, Hermes, or OpenClaw workspaces, see [Situla](../situla/README.md). Situla is
a standalone TypeScript project included under this tutorial category because
it connects directly to AgentKit Tool Sandbox.

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

### List Session Snapshots

Run with named arguments:

```bash
python3 list_snapshots.py \
  --tool-id <tool-id>
```

Filter by UserSessionId:

```bash
python3 list_snapshots.py \
  --tool-id <tool-id> \
  --user-session-id <user-session-id>
```

Filter by internal SessionId (sandbox session id):

```bash
python3 list_snapshots.py \
  --tool-id <tool-id> \
  --session-id <session-id>
```

Filter by creation time range (RFC3339 format):

```bash
python3 list_snapshots.py \
  --tool-id <tool-id> \
  --create-time-after 2025-01-01T00:00:00Z \
  --create-time-before 2025-12-31T23:59:59Z
```

Run with positional arguments (TOOL_ID [USER_SESSION_ID]):

```bash
python3 list_snapshots.py <tool-id> <user-session-id>
```

Run from the repository root:

```bash
python3 python/01-tutorials/04-agentkit-tools/code_sandbox/list_snapshots.py \
  --tool-id <tool-id>
```

### Restore Session from Snapshot

Run with named arguments:

```bash
python3 restore_from_snapshot.py \
  --tool-id <tool-id> \
  --snapshot-id <snapshot-id>
```

Run with positional arguments:

```bash
python3 restore_from_snapshot.py <tool-id> <snapshot-id>
```

Restore with a custom TTL:

```bash
python3 restore_from_snapshot.py \
  --tool-id <tool-id> \
  --snapshot-id <snapshot-id> \
  --ttl 3600
```

Create a brand-new instance from the snapshot:

```bash
python3 restore_from_snapshot.py \
  --tool-id <tool-id> \
  --snapshot-id <snapshot-id> \
  --create-new-instance
```

Run from the repository root:

```bash
python3 python/01-tutorials/04-agentkit-tools/code_sandbox/restore_from_snapshot.py \
  --tool-id <tool-id> \
  --snapshot-id <snapshot-id>
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

`list_snapshots.py`:

```text
--tool-id               AgentKit sandbox tool ID (required).
--user-session-id       Filter snapshots by UserSessionId.
--session-id            Filter snapshots by the internal SessionId (sandbox session id).
--page-size             Page size per request. Default: 100.
--region                Volcano Engine region. Defaults to VOLCENGINE_REGION or SDK config.
--access-key            Volcano Engine access key. Defaults to VOLCENGINE_ACCESS_KEY.
--secret-key            Volcano Engine secret key. Defaults to VOLCENGINE_SECRET_KEY.
--session-token         STS session token. Defaults to VOLCENGINE_SESSION_TOKEN.
--create-time-after     Only list snapshots created after this time (RFC3339 string, e.g. 2025-01-01T00:00:00Z).
--create-time-before    Only list snapshots created before this time (RFC3339 string).
```

`restore_from_snapshot.py`:

```text
--tool-id               AgentKit sandbox tool ID (required).
--snapshot-id           Snapshot ID to restore from (required).
--ttl                   Session TTL in seconds. Default: 28800.
--create-new-instance   Create a brand-new sandbox instance from the snapshot
                        instead of reusing the previous instance ID.
--region                Volcano Engine region. Defaults to VOLCENGINE_REGION or SDK config.
--access-key            Volcano Engine access key. Defaults to VOLCENGINE_ACCESS_KEY.
--secret-key            Volcano Engine secret key. Defaults to VOLCENGINE_SECRET_KEY.
--session-token         STS session token. Defaults to VOLCENGINE_SESSION_TOKEN.
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

### List Session Snapshots

List all snapshots for a tool:

```bash
python3 list_snapshots.py \
  --tool-id tl-xxxxxxxx
```

Filter by UserSessionId:

```bash
python3 list_snapshots.py \
  --tool-id tl-xxxxxxxx \
  --user-session-id demo-session
```

Filter by creation time range with a custom page size:

```bash
python3 list_snapshots.py \
  --tool-id tl-xxxxxxxx \
  --create-time-after 2025-06-01T00:00:00Z \
  --create-time-before 2025-07-01T00:00:00Z \
  --page-size 50
```

Run with positional arguments:

```bash
python3 list_snapshots.py tl-xxxxxxxx demo-session
```

### Restore Session from Snapshot

Restore with the default TTL:

```bash
python3 restore_from_snapshot.py \
  --tool-id tl-xxxxxxxx \
  --snapshot-id snap-xxxxxxxx
```

Restore with a custom TTL and create a new instance:

```bash
python3 restore_from_snapshot.py \
  --tool-id tl-xxxxxxxx \
  --snapshot-id snap-xxxxxxxx \
  --ttl 3600 \
  --create-new-instance
```

Run with positional arguments:

```bash
python3 restore_from_snapshot.py tl-xxxxxxxx snap-xxxxxxxx
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

`list_snapshots.py` prints JSON containing `tool_id`, `total_count` (total number of snapshots), and `snapshots` (the list of snapshots). The script automatically paginates through all results.

Example:

```json
{
  "tool_id": "tl-xxxxxxxx",
  "total_count": 2,
  "snapshots": [
    {
      "SnapshotId": "snap-aaaaaaaa",
      "ToolId": "tl-xxxxxxxx",
      "UserSessionId": "demo-session",
      "SessionId": "ss-aaaaaaaa",
      "CreateTime": "2025-06-15T10:30:00Z",
      "Status": "success"
    },
    {
      "SnapshotId": "snap-bbbbbbbb",
      "ToolId": "tl-xxxxxxxx",
      "UserSessionId": "demo-session",
      "SessionId": "ss-bbbbbbbb",
      "CreateTime": "2025-06-10T08:00:00Z",
      "Status": "success"
    }
  ]
}
```

`restore_from_snapshot.py` prints JSON containing `action`, `tool_id`, `snapshot_id`, `session_id` (user session ID), `instance_id` (sandbox instance ID), `endpoint`, `internal_endpoint`, `status`, `expire_at`, `created_at`, and `raw` (raw response data).

Example:

```json
{
  "action": "restored_from_snapshot",
  "tool_id": "tl-xxxxxxxx",
  "snapshot_id": "snap-xxxxxxxx",
  "session_id": "demo-session",
  "instance_id": "ss-yyyyyyyy",
  "endpoint": "https://example.endpoint",
  "internal_endpoint": null,
  "status": "running",
  "expire_at": "2025-06-15T18:30:00Z",
  "created_at": "2025-06-15T10:30:00Z",
  "raw": {
    "resume_response": { "...": "..." },
    "session": { "...": "..." }
  }
}
```

`codex_ws_tui.py --message` prints the plain-text Codex reply; interactive mode continuously shows the conversation in the terminal.
