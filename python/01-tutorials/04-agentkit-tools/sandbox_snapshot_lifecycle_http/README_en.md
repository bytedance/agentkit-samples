# Sandbox Session and Snapshot Lifecycle HTTP Example

This directory provides sandbox session and snapshot lifecycle scripts that do
not depend on `agentkit.sdk`. The scripts call the AgentKit Tools OpenAPI
directly. `_http_client.py` implements HTTP requests, HMAC-SHA256 request
signing, error parsing, and basic retries locally in this example.

This example is parallel to the SDK-based `../sandbox_snapshot_lifecycle`
example. It keeps the same execution order and state-file behavior. Signed
endpoint `Authorization` query parameters are redacted before output or state
persistence.

The sequence is: **create session -> invoke session -> create snapshot -> list
and get snapshots -> restore after the session lifecycle ends -> invoke session
again -> delete snapshot -> delete session**. Invocation after restoration
reuses script 02.

**Restoration is only allowed after the original session lifecycle ends.** This
example lets the TTL expire and the instance finish terminating before restoring
the original instance with `ResumeSessionFromSnapshot`.
**Calling `DeleteSession` also deletes the session's snapshots. Keep session
deletion as the final step; do not use it to end the lifecycle before
restoration.**

## Install Dependencies

```bash
pip install -r python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/requirements.txt
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

- `AGENTKIT_SESSION_TTL_SECONDS`: session and restored-instance TTL; defaults to
  `28800` seconds (8 hours). Script 02 does not send a TTL.
- `AGENTKIT_USER_SESSION_ID`: logical user session ID; script 01 generates one
  when omitted.
- `AGENTKIT_INVOKE_CODE`: Python code executed by script 02; defaults to
  `print('Hello from AgentKit sandbox!')`.
- `AGENTKIT_INVOKE_TIMEOUT_SECONDS`: code execution timeout for script 02;
  defaults to 30 seconds and must be a positive integer.
- `AGENTKIT_INVOKE_KERNEL_NAME`: kernel used by script 02; defaults to `python3`.
- `AGENTKIT_LIFECYCLE_STATE`: shared state JSON path; defaults to
  `.sandbox_snapshot_state.json` in this directory.
- `AGENTKIT_WAIT_TIMEOUT_SECONDS`: readiness timeout; defaults to 600 seconds.
- `AGENTKIT_POLL_INTERVAL_SECONDS`: readiness polling interval; defaults to 5
  seconds.
- `AGENTKIT_HTTP_TIMEOUT_SECONDS`: per-request HTTP timeout; defaults to 30
  seconds.
- `AGENTKIT_HTTP_RETRIES`: retry count for connection errors, HTTP 429, and HTTP
  503; defaults to 2.

`InvokeTool`, `AsyncExecCommand`, and `ViewAsyncCommand` use a separate data-plane endpoint: Volcengine uses
`https://agentkit.<region>.volces.com`; the [BytePlus documentation](https://docs.byteplus.com/en/docs/AgentKit/InvokeTool_-_Executes_command_in_a_tool)
specifies `https://agentkit.ap-southeast-1.bytepluses.com` for Singapore,
which differs from the management host `agentkit.ap-southeast-1.byteplusapi.com`.
Both scripts numbered 02 select the invocation endpoint for the cloud and region automatically.
The API version remains `2025-10-30`. A host override is normally unnecessary;
if `BYTEPLUS_AGENTKIT_HOST` or `VOLCENGINE_AGENTKIT_HOST` is set, the selected
host must support the corresponding data-plane actions.

## Run Code In A Session

`02_invoke_session.py` calls `InvokeTool` to execute Python code in the sandbox
instance recorded in the state file. Run it after script 01 creates the instance
and waits for readiness, or again after script 05 restores the instance and
waits for readiness. The sandbox image must support the `/v1/jupyter/execute`
interface used by `RunCode` and the selected Python kernel.

The request sends `ToolId`, the saved `instance_id` as `SessionId`,
`OperationType="RunCode"`, and a JSON-string `OperationPayload` containing
`code`, `timeout`, and `kernel_name`. The script explicitly selects the existing
`SessionId` and verifies that the response returns the same instance ID. It does
not use `UserSessionId` to resolve or create an instance.

Run from the repository root, optionally customizing the code:

```bash
export AGENTKIT_INVOKE_CODE="print(sum([1, 2, 3]))"
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/02_invoke_session.py
```

The script saves `invoked_at`, `invoke_response`, and `invoke_result`, parsing
the returned `Result` JSON string for readable output. Standard output is
typically found in `invoke_result.data.outputs`. API errors are reported
directly. Execution results with `success: false` or `data.status: error` cause
the script to exit with an error after saving and printing the result.

## Run a Shell command asynchronously

`02_async_invoke_session.py` submits a command through
[AsyncExecCommand](https://docs.volcengine.com/docs/agentkit/AsyncExecCommand_-_Asynchronously_executes_a_Shell_command_in_a_tool?lang=zh),
then repeatedly calls [ViewAsyncCommand](https://docs.volcengine.com/docs/agentkit/ViewAsyncCommand_-_Queries_the_execution_result_of_an_asynchronous_command?lang=zh)
with the returned `TaskId` until completion or a local timeout.
Run after step 01 creates a ready Session, or after step 05 restores the Session and waits for readiness.
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

Run from the repository root as an alternative or addition to each `02_invoke_session.py` invocation in the main flow:

```bash
export AGENTKIT_ASYNC_COMMAND="sleep 20 && echo 'Hello from AgentKit sandbox!'"
export AGENTKIT_ASYNC_EXEC_DIR=/tmp
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/02_async_invoke_session.py
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
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/02_async_invoke_session.py --view-only
```

`--view-only` ignores command/directory settings, submits no new command, and
still updates query results. Running without it submits a new task and replaces
the saved task record; previous remote tasks are not cancelled.

Wait for the asynchronous command to finish before step 03 creates a snapshot.
Step 05 still restores only after the original Session lifecycle ends. Once
restored and ready, run the asynchronous entry again without `--view-only` to
submit a new verification task. Do not assume snapshot restoration restores an
old task execution or query record. Keep Session deletion as the final step.

## Run The Main Flow In Order

The default TTL is 8 hours. To shorten the demo wait, set a shorter TTL
**before** running script 01, for example:

```bash
export AGENTKIT_SESSION_TTL_SECONDS=60
export AGENTKIT_WAIT_TIMEOUT_SECONDS=900
```

Leave enough time for steps 01-04. Changing this environment variable after
creation does not change the original Session expiration time. It only affects
later create or restore requests.

Run steps 01-04 from the repository root to create and invoke the session, then
create and query snapshots:

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/01_create_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/02_invoke_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/03_create_snapshot.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/04_list_and_get_snapshot.py
```

Wait for the original session's TTL to expire and its lifecycle to end before
running step 05. The `session.ExpireAt` field in script 01's output shows the
expiry time when returned by the service:

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/05_restore_from_snapshot.py
```

If step 05 runs too early, the backend returns
`InvalidSnapshot.InstanceAlreadyExists` (the instance is still in use) or
`InvalidSnapshot.InstanceTerminating` (termination is in progress). The script
retries at the polling interval until restoration is allowed or the wait times
out. After a timeout, rerun step 05 once the session lifecycle ends, or increase
`AGENTKIT_WAIT_TIMEOUT_SECONDS`. Other API errors propagate immediately.

After step 05 succeeds, run script 02 again to confirm that the restored
instance can execute code:

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/02_invoke_session.py
```

After verification, delete the snapshot and restored session in order:

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/06_delete_snapshot.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/07_delete_session.py
```

Script purposes:

1. `01_create_session.py`: checks that the Tool has snapshots enabled, creates a
   Session, and waits until the sandbox instance becomes `Ready`.
2. `02_invoke_session.py`: executes Python code in the existing session through
   `InvokeTool`, verifies the instance ID, and saves the result; run it again
   after restoration.
   Step 02 can also use `02_async_invoke_session.py` to submit a Shell command and poll; run it again after restoration.
3. `03_create_snapshot.py`: creates a snapshot for the Session's sandbox
   instance and waits until the snapshot becomes `Ready`.
4. `04_list_and_get_snapshot.py`: lists all snapshots under the Tool with
   pagination, then gets the newly created snapshot.
5. `05_restore_from_snapshot.py`: waits for the original Session lifecycle to
   end, sends `CreateNewInstance=false` to restore the original sandbox from the
   snapshot, and verifies that the returned `SessionId` matches script 01. If
   the instance is still active or terminating asynchronously, the script waits
   and retries.
6. `06_delete_snapshot.py`: deletes the recorded snapshot, follows pagination,
   and waits until that snapshot no longer appears under the Tool. It does not
   delete the sandbox instance restored by step 05.
7. `07_delete_session.py`: finally deletes the Session. `DeleteSession` also
   deletes any remaining snapshots that belong to the Session, so it must not be
   used as the lifecycle-ending step before step 05 restore.

For pausing and resuming a running session, see the adjacent
[sandbox_lifecycle_http](../sandbox_lifecycle_http/README_en.md) example.

## HTTP Request Shape

All APIs use `POST /?Action=<Action>&Version=2025-10-30`. Request bodies use
PascalCase JSON fields, for example:

```json
{
  "ToolId": "t-xxxxxxxx",
  "Ttl": 28800,
  "TtlUnit": "second",
  "UserSessionId": "snapshot-demo-xxxx"
}
```

Business data is read from the response `Result` field. If
`ResponseMetadata.Error` is present, the HTTP client raises an exception with
the action, error code, and error message.

## State File

The eight scripts share `.sandbox_snapshot_state.json` to pass the `tool_id`,
logical user session ID, sandbox instance ID, and snapshot ID. Script 02 also
saves `invoked_at`, `invoke_response`, and `invoke_result`; invoking it again
updates these fields. This file is ignored by the `.gitignore` in this
directory.

If you rerun script 01 without `AGENTKIT_USER_SESSION_ID`, it generates a new
logical session ID, creates a new sandbox instance, and overwrites the state
file. Previously created instances are not deleted automatically.
