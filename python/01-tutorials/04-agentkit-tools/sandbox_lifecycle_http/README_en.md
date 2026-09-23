# Sandbox Instance (Session) Lifecycle HTTP Example

This directory contains seven scripts that do not depend on `agentkit.sdk`. They
cover creating, querying, invoking, pausing, resuming, and deleting sessions.
`02_list_and_get_session.py` is read-only. The scripts call the AgentKit Tools
OpenAPI directly. `_http_client.py` implements HTTP requests, HMAC-SHA256 request
signing, error parsing, and basic retries locally in this example. Signed
endpoint `Authorization` query parameters are redacted before output or state
persistence.

This example is parallel to the SDK-based `../sandbox_lifecycle` example. It
keeps the same execution order and state-file behavior.

`InvokeTool` runs code in an existing Session. `PauseSession` / `ResumeSession`
pause and resume the same Session.

For Chinese instructions, see [README.md](README.md).

## Install Dependencies

Python 3.10 or later is required. Install from the repository root:

```bash
pip install -r python/01-tutorials/04-agentkit-tools/sandbox_lifecycle_http/requirements.txt
```

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

- `AGENTKIT_SESSION_TTL_SECONDS`: TTL passed when script 01 creates a session;
  defaults to `28800` (8 hours). Scripts 03 and 05 do not send a TTL when
  invoking or resuming the session.
- `AGENTKIT_USER_SESSION_ID`: logical session ID used only by script 01, which
  generates one when omitted.
- `AGENTKIT_SESSION_ID`: instance ID used only by script 02; overrides the saved
  `instance_id`.
- `AGENTKIT_INVOKE_CODE`: Python code executed by script 03; defaults to
  `print('Hello from AgentKit sandbox!')`.
- `AGENTKIT_INVOKE_TIMEOUT_SECONDS`: code execution timeout for script 03;
  defaults to 30 seconds and must be a positive integer.
- `AGENTKIT_INVOKE_KERNEL_NAME`: kernel used by script 03; defaults to `python3`.
- `AGENTKIT_SANDBOX_TOOL_ID`: compatible alias for `AGENTKIT_TOOL_ID`; if both
  are set, they must match.
- `AGENTKIT_LIFECYCLE_STATE`: shared state JSON path; defaults to
  `.sandbox_state.json` in the script directory, regardless of the working
  directory. The query script only reads this file.
- `AGENTKIT_WAIT_TIMEOUT_SECONDS`: timeout for create, pause, and resume state
  polling; defaults to 600 seconds. The delete script does not poll for deletion.
- `AGENTKIT_POLL_INTERVAL_SECONDS`: readiness polling interval; defaults to 5
  seconds.
- `AGENTKIT_HTTP_TIMEOUT_SECONDS`: per-request HTTP timeout; defaults to 30
  seconds.
- `AGENTKIT_HTTP_RETRIES`: retry count for connection errors, HTTP 429, and HTTP
  503; defaults to 2.

When switching clouds or regions, update the tool ID and select a separate state
file with `AGENTKIT_LIFECYCLE_STATE`. Start lifecycle operations from script 01;
querying an existing session does not require creating a new instance.

## List Sessions And Get Session Details

`02_list_and_get_session.py` follows `ListSessions` pagination to list all
sessions under the tool, then calls `GetSession` for the selected instance. It
only reads cloud resources and local state; it does not update the state file.

Run from the repository root:

```bash
pip install -r python/01-tutorials/04-agentkit-tools/sandbox_lifecycle_http/requirements.txt
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle_http/02_list_and_get_session.py
```

By default, the script uses `tool_id` and `instance_id` from this directory's
state file, or the file selected by `AGENTKIT_LIFECYCLE_STATE`. Run it after
creating, pausing, or resuming a session.

You can also select an existing session without running the create script:

```bash
export AGENTKIT_TOOL_ID=t-xxxxxxxx
export AGENTKIT_SESSION_ID="<SessionId>"
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle_http/02_list_and_get_session.py
```

`AGENTKIT_SESSION_ID` overrides the saved `instance_id`. Use the instance's API
`SessionId`, not its logical `UserSessionId`. The existing consistency check
between the environment and saved tool ID still applies. When neither an
explicit nor a saved instance ID is available, the script only lists sessions
and outputs `session: null`. Empty lists are valid; `GetSession` API errors are
reported directly. Signed endpoints in both the list and details are redacted.

## Run code in a session

`InvokeTool`, `AsyncExecCommand`, and `ViewAsyncCommand` use a separate data-plane endpoint: Volcengine uses
`https://agentkit.<region>.volces.com`; the [BytePlus documentation](https://docs.byteplus.com/en/docs/AgentKit/InvokeTool_-_Executes_command_in_a_tool)
specifies `https://agentkit.ap-southeast-1.bytepluses.com` for Singapore,
which differs from the management host `agentkit.ap-southeast-1.byteplusapi.com`.
Both scripts numbered 03 select the invocation endpoint for the cloud and region automatically.
The API version remains `2025-10-30`. A host override is normally unnecessary;
if `BYTEPLUS_AGENTKIT_HOST` or `VOLCENGINE_AGENTKIT_HOST` is set, the selected
host must support the corresponding data-plane actions.

`03_invoke_session.py` calls `InvokeTool` to execute Python code in the sandbox
instance recorded in the state file. Create the instance with script 01 first
and ensure it is ready. If it is paused, run script 05 to resume it before
invoking script 03. The sandbox image must support the `/v1/jupyter/execute`
interface used by `RunCode` and the selected Python kernel.

The request sends `ToolId`, the saved `instance_id` as `SessionId`,
`OperationType="RunCode"`, and a JSON-string `OperationPayload` containing
`code`, `timeout`, and `kernel_name`. The script explicitly selects the existing
`SessionId` and verifies that the response returns the same instance ID. It does
not use `UserSessionId` to resolve or create an instance.

Run from the repository root, optionally customizing the code:

```bash
export AGENTKIT_INVOKE_CODE="print(sum([1, 2, 3]))"
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle_http/03_invoke_session.py
```

The script saves `invoked_at`, `invoke_response`, and `invoke_result`, parsing
the returned `Result` JSON string for readable output. Standard output is
typically found in `invoke_result.data.outputs`. API errors are reported
directly. Execution results with `success: false` or `data.status: error` cause
the script to exit with an error after saving and printing the result.

## Run a Shell command asynchronously

`03_async_invoke_session.py` submits a command through
[AsyncExecCommand](https://docs.volcengine.com/docs/agentkit/AsyncExecCommand_-_Asynchronously_executes_a_Shell_command_in_a_tool?lang=zh),
then repeatedly calls [ViewAsyncCommand](https://docs.volcengine.com/docs/agentkit/ViewAsyncCommand_-_Queries_the_execution_result_of_an_asynchronous_command?lang=zh)
with the returned `TaskId` until completion or a local timeout.
First create a ready Session with step 01; if paused, resume it with step 05.
The sandbox image must support asynchronous Shell execution through these APIs.
Both actions reuse `_http_client.py` signing, error handling, and data-plane routing without the AgentKit SDK.

Submission sends top-level `ToolId`, the saved `instance_id` as `SessionId`,
`Command`, and optional `ExecDir`. Queries send the same `ToolId`, `SessionId`,
and returned `TaskId`. Neither request sends `UserSessionId` or `Ttl`.
The response tool, instance, and task IDs are validated. Both Volcengine and
BytePlus reuse this directory's credential, region, and host configuration.

Optional environment variables:

- `AGENTKIT_ASYNC_COMMAND`: Shell command; defaults to `sleep 20 && echo 'Hello from AgentKit sandbox!'` and must not be empty.
- `AGENTKIT_ASYNC_EXEC_DIR`: existing working directory inside the sandbox; when omitted, the sandbox default is used.
- `AGENTKIT_ASYNC_WAIT_TIMEOUT_SECONDS`: local polling timeout; defaults to 600 seconds.
- `AGENTKIT_ASYNC_POLL_INTERVAL_SECONDS`: query interval; defaults to 2 seconds.
  Both timing settings must be positive integers and do not control remote execution time or Session TTL.

Run from the repository root as an alternative or addition to each `03_invoke_session.py` invocation in the main flow:

```bash
export AGENTKIT_ASYNC_COMMAND="sleep 20 && echo 'Hello from AgentKit sandbox!'"
export AGENTKIT_ASYNC_EXEC_DIR=/tmp
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle_http/03_async_invoke_session.py
```

Terminal output uses `*` separators for submission (or loading a saved task),
polling, and completion. Each query prints its number, status, and elapsed time;
`-` separators mark combined stdout/stderr output and the state file path.
Status comparisons are case-insensitive: `running` keeps polling and ignores
exit codes; `succeeded` or `completed` requires `ExitCode=0` to succeed.
`failed`, `unknown`, unrecognized statuses, or missing/nonzero completion exit
codes raise an error after saving and printing results. API errors surface directly.

Submission immediately saves `async_task_id`, `async_invoked_at`, and
`async_invoke_response`. Each query saves `async_viewed_at` and
`async_view_response` in the existing state file, or the file selected by
`AGENTKIT_LIFECYCLE_STATE`. Full responses remain in that file; combined output
is in `async_view_response.Output`. A local timeout or interruption does not
cancel the remote task. Continue polling the saved task with:

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle_http/03_async_invoke_session.py --view-only
```

`--view-only` ignores command/directory settings, submits no new command, and
still updates query results. Running without it submits a new task and replaces
the saved task record; previous remote tasks are not cancelled.

Wait for the asynchronous command to finish before pausing or deleting the Session.

## Scripts And Execution Order

The seven scripts are:

| Script | Behavior |
| --- | --- |
| `01_create_session.py` | Create a session with an eight-hour default TTL, wait until it is ready, and save the instance ID. |
| `02_list_and_get_session.py` | List all session pages and get the selected instance's details; read-only. |
| `03_invoke_session.py` | Execute Python code in the existing session through `InvokeTool`, verify the instance ID, and save the result. |
| `03_async_invoke_session.py` | Submit a Shell command asynchronously and poll; `--view-only` queries the saved task. |
| `04_pause_session.py` | Pause the saved session, wait for `Paused`, and record `paused_at`. |
| `05_resume_session.py` | Require `paused_at`, resume the same session, verify the instance ID, and wait until it is ready. |
| `06_delete_session.py` | Call `DeleteSession` using the tool ID and saved `instance_id`, then save the response without waiting for backend deletion. |

To verify invocation, pause, and resume, run **01 -> 02 -> 03 -> 04 -> 05 -> 02 -> 03**:
create, query, and invoke the session, pause and resume it, then query and
invoke the resumed instance again. Use script 06 for cleanup after this
verification.

Run from the repository root:

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle_http/01_create_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle_http/02_list_and_get_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle_http/03_invoke_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle_http/04_pause_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle_http/05_resume_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle_http/02_list_and_get_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle_http/03_invoke_session.py
```

Clean up the instance recorded in the state file with this command:

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle_http/06_delete_session.py
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
`ResponseMetadata.Error` is present, the HTTP client raises an exception with
the action, error code, and error message.

## State File

The default state file is `.sandbox_state.json` in this directory. It stores
`tool_id`, `user_session_id`, `instance_id`, lifecycle timestamps, and API
responses. Scripts 01, both 03 scripts, 04, 05, and 06 write state; script 02 only reads it.
This file is ignored by the `.gitignore` in this directory.

Scripts 03, 04, 05, and 06 select the instance using the saved `instance_id`; neither
`AGENTKIT_USER_SESSION_ID` nor `AGENTKIT_SESSION_ID` changes their target.

Running script 01 again without `AGENTKIT_USER_SESSION_ID` generates a new
logical session ID, creates a new sandbox instance, and overwrites the state
file. Previously created instances are not automatically deleted.
