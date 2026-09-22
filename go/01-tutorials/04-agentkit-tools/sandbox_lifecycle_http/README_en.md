# Sandbox Instance (Session) Lifecycle HTTP Example for Go

This directory provides Go examples that do not depend on the AgentKit SDK. They
cover creating, querying, invoking, pausing, resuming, and deleting sessions. The code
calls the AgentKit Tools OpenAPI directly. The standard-library HTTP client
under `internal/lifecycle` implements request sending, HMAC-SHA256 request
signing, error parsing, basic retries, state-file handling, and polling.

This example is parallel to
`python/01-tutorials/04-agentkit-tools/sandbox_lifecycle_http`. It keeps the
same API order and state-file behavior. Signed endpoint `Authorization` query
parameters are redacted before output or state persistence.

`InvokeTool` runs code in an existing Session. `PauseSession` / `ResumeSession`
pause and resume the same Session.

## Requirements

- Go 1.20+.
- No AgentKit SDK installation is required.
- The example uses only the Go standard library, so it has no extra dependency
  or `go.sum`.

## Volcengine Configuration

Volcengine is the default provider. You can also set it explicitly:

```bash
export AGENTKIT_CLOUD_PROVIDER=volcengine
export VOLCENGINE_ACCESS_KEY=<your-access-key>
export VOLCENGINE_SECRET_KEY=<your-secret-key>
export AGENTKIT_TOOL_ID=t-xxxxxxxx
```

Legacy variable names are also supported:

- `VOLC_ACCESSKEY`
- `VOLC_SECRETKEY`
- `VOLC_SESSIONTOKEN`
- `VOLC_REGION`

Optional settings:

- `VOLCENGINE_SESSION_TOKEN`: STS session token.
- `VOLCENGINE_AGENTKIT_REGION` or `AGENTKIT_REGION`: AgentKit OpenAPI signing
  region; defaults to `cn-beijing`.
- `VOLCENGINE_AGENTKIT_HOST`: custom OpenAPI host; defaults to
  `open.volcengineapi.com`.
- `VOLCENGINE_AGENTKIT_SERVICE`: signing service; defaults to `agentkit`.
- `VOLCENGINE_AGENTKIT_API_VERSION`: OpenAPI version; defaults to `2025-10-30`.
- `VOLCENGINE_AGENTKIT_SCHEME`: request scheme; defaults to `https`.

## BytePlus Configuration

```bash
export AGENTKIT_CLOUD_PROVIDER=byteplus
export BYTEPLUS_ACCESS_KEY=<your-access-key>
export BYTEPLUS_SECRET_KEY=<your-secret-key>
export AGENTKIT_TOOL_ID=t-xxxxxxxx
```

Optional settings:

- `BYTEPLUS_SESSION_TOKEN`: STS session token.
- `BYTEPLUS_AGENTKIT_REGION`, `AGENTKIT_REGION`, or `BYTEPLUS_REGION`: AgentKit
  OpenAPI signing region; defaults to `ap-southeast-1`.
- `BYTEPLUS_AGENTKIT_HOST`: custom OpenAPI host; defaults to
  `agentkit.<region>.byteplusapi.com`.
- `BYTEPLUS_AGENTKIT_SERVICE`: signing service; defaults to `agentkit`.
- `BYTEPLUS_AGENTKIT_API_VERSION`: OpenAPI version; defaults to `2025-10-30`.
- `BYTEPLUS_AGENTKIT_SCHEME`: request scheme; defaults to `https`.

## Lifecycle Settings

- `AGENTKIT_SESSION_TTL_SECONDS`: TTL passed when command 01 creates a session;
  defaults to `28800` (8 hours). Commands 03 and 05 do not send a TTL when
  invoking or resuming the session.
- `AGENTKIT_USER_SESSION_ID`: logical session ID used only by command 01, which
  generates one when omitted.
- `AGENTKIT_SESSION_ID`: instance ID used only by command 02; overrides the saved
  `instance_id`.
- `AGENTKIT_INVOKE_CODE`: Python code executed by command 03; defaults to
  `print('Hello from AgentKit sandbox!')`.
- `AGENTKIT_INVOKE_TIMEOUT_SECONDS`: code execution timeout for command 03;
  defaults to 30 seconds and must be a positive integer.
- `AGENTKIT_INVOKE_KERNEL_NAME`: kernel used by command 03; defaults to
  `python3`.
- `AGENTKIT_SANDBOX_TOOL_ID`: compatible alias for `AGENTKIT_TOOL_ID`; if both
  are set, they must match.
- `AGENTKIT_LIFECYCLE_STATE`: shared state JSON path; defaults to
  `.sandbox_state.json` in this directory, regardless of the working directory.
  The query command only reads this file.
- `AGENTKIT_WAIT_TIMEOUT_SECONDS`: timeout for create, pause, and resume state
  polling; defaults to 600 seconds. The delete command does not poll for
  deletion.
- `AGENTKIT_POLL_INTERVAL_SECONDS`: readiness polling interval; defaults to 5
  seconds.
- `AGENTKIT_HTTP_TIMEOUT_SECONDS`: per-request HTTP timeout; defaults to 30
  seconds.
- `AGENTKIT_HTTP_RETRIES`: retry count for connection errors, HTTP 429, and HTTP
  503; defaults to 2.

Volcengine `InvokeTool` uses the separate data-plane endpoint
`https://agentkit.<region>.volces.com`. Command 03 selects that endpoint
automatically. If you override `VOLCENGINE_AGENTKIT_HOST`, the selected host
must also support `InvokeTool`.

When switching clouds or regions, update the tool ID and select a separate state
file with `AGENTKIT_LIFECYCLE_STATE`. Start lifecycle operations from command
01; querying an existing session does not require creating a new instance.

## List Sessions And Get Session Details

`02_list_and_get_session` follows `ListSessions` pagination to list all sessions
under the tool, then calls `GetSession` for the selected instance. It only reads
cloud resources and local state; it does not update the state file.

You can also select an existing session without running the create command:

```bash
export AGENTKIT_TOOL_ID=t-xxxxxxxx
export AGENTKIT_SESSION_ID="<SessionId>"
go run ./cmd/02_list_and_get_session
```

`AGENTKIT_SESSION_ID` overrides the saved `instance_id`. Use the instance's API
`SessionId`, not its logical `UserSessionId`. The existing consistency check
between the environment and saved tool ID still applies. When neither an
explicit nor a saved instance ID is available, the command only lists sessions
and outputs `session: null`.

## Run Code In A Session

`03_invoke_session` calls `InvokeTool` to execute Python code in the sandbox
instance recorded in the state file. Create the instance with command 01 first
and ensure it is ready. If it is paused, run command 05 to resume it before
invoking command 03. The sandbox image must support the `/v1/jupyter/execute`
interface used by `RunCode` and the selected Python kernel.

The request sends `ToolId`, the saved `instance_id` as `SessionId`,
`OperationType="RunCode"`, and a JSON-string `OperationPayload` containing
`code`, `timeout`, and `kernel_name`. The command explicitly selects the
existing `SessionId` and verifies that the response returns the same instance
ID. It does not use `UserSessionId` to resolve or create an instance.

Run from this directory, optionally customizing the code:

```bash
export AGENTKIT_INVOKE_CODE="print(sum([1, 2, 3]))"
go run ./cmd/03_invoke_session
```

The command saves `invoked_at`, `invoke_response`, and `invoke_result`, parsing
the returned `Result` JSON string for readable output. Standard output is
typically found in `invoke_result.data.outputs`. API errors are reported
directly. Execution results with `success: false` or `data.status: error` cause
the command to exit with an error after saving and printing the result.

## Scripts And Execution Order

The six commands are:

| Command | Behavior |
| --- | --- |
| `01_create_session` | Create a session with an eight-hour default TTL, wait until it is ready, and save the instance ID. |
| `02_list_and_get_session` | List all session pages and get the selected instance's details; read-only. |
| `03_invoke_session` | Execute Python code in the existing session through `InvokeTool`, verify the instance ID, and save the result. |
| `04_pause_session` | Pause the saved session, wait for `Paused`, and record `paused_at`. |
| `05_resume_session` | Require `paused_at`, resume the same session, verify the instance ID, and wait until it is ready. |
| `06_delete_session` | Call `DeleteSession` using the tool ID and saved `instance_id`, then save the response without waiting for backend deletion. |

To verify invocation, pause, and resume, run **01 -> 02 -> 03 -> 04 -> 05 -> 02 -> 03**.
Use command 06 for cleanup after this verification.

Run from this directory:

```bash
go run ./cmd/01_create_session
go run ./cmd/02_list_and_get_session
go run ./cmd/03_invoke_session
go run ./cmd/04_pause_session
go run ./cmd/05_resume_session
go run ./cmd/02_list_and_get_session
go run ./cmd/03_invoke_session
```

Clean up the instance recorded in the state file with this command:

```bash
go run ./cmd/06_delete_session
```

## HTTP Request Shape

All APIs use `POST /?Action=<Action>&Version=2025-10-30`. Request bodies use
PascalCase JSON fields, for example:

```json
{
  "ToolId": "t-xxxxxxxx",
  "Ttl": 28800,
  "TtlUnit": "second",
  "UserSessionId": "session-demo-xxxx"
}
```

Business data is read from the response `Result` field. If
`ResponseMetadata.Error` is present, the HTTP client returns an error with the
action, error code, and error message.

## State File

The default state file is `.sandbox_state.json` in this directory. It stores
`tool_id`, `user_session_id`, `instance_id`, lifecycle timestamps, and API
responses. Commands 01, 03, 04, 05, and 06 write state; command 02 only reads it.
This file is ignored by the `.gitignore` in this directory.

Commands 03, 04, 05, and 06 select the instance using the saved `instance_id`;
neither `AGENTKIT_USER_SESSION_ID` nor `AGENTKIT_SESSION_ID` changes their
target.

Running command 01 again without `AGENTKIT_USER_SESSION_ID` generates a new
logical session ID, creates a new sandbox instance, and overwrites the state
file. Previously created instances are not deleted automatically.

## Local Verification

```bash
go test ./...
```
