# Sandbox session and snapshot lifecycle scripts

These eight scripts demonstrate the sandbox session and snapshot lifecycle
in order. They use the `agentkit.sdk.tools` client from `agentkit-sdk-python` and never store
AK/SK credentials. Signed endpoint `Authorization` query parameters are redacted
before output or state persistence.

The sequence is: **create session → invoke session → create snapshot → list and get
snapshots → restore after the session lifecycle ends → invoke session again →
delete snapshot → delete session**. Invocation after restoration reuses script 02.

**Restoration is only allowed after the original session lifecycle ends.** This
example lets the TTL expire and the instance finish terminating before restoring
the original instance with `ResumeSessionFromSnapshot`.
**Calling `DeleteSession` also deletes the session's snapshots. Keep session
deletion as the final step; do not use it to end the lifecycle before restoration.**

For Chinese instructions, see [README.md](README.md).

## Install dependencies

This example uses `agentkit-sdk-python==0.8.7`. Install dependencies from the repository root:

```bash
pip install -r python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/requirements.txt
```

## Environment

Choose the configuration for the cloud hosting your sandbox. All eight scripts
share the same credentials and region configuration.

**BytePlus:**

```bash
export AGENTKIT_CLOUD_PROVIDER=byteplus
export BYTEPLUS_ACCESS_KEY="<Your Access Key>"
export BYTEPLUS_SECRET_KEY="<Your Secret Key>"
export BYTEPLUS_REGION=ap-southeast-1
export AGENTKIT_TOOL_ID=t-xxxxxxxx
```

**Volcengine:**

```bash
export AGENTKIT_CLOUD_PROVIDER=volcengine
export VOLCENGINE_ACCESS_KEY="<Your Access Key>"
export VOLCENGINE_SECRET_KEY="<Your Secret Key>"
export VOLCENGINE_REGION=cn-beijing
export AGENTKIT_TOOL_ID=t-xxxxxxxx
```

The tool must belong to the selected cloud, account, and region, with snapshots
enabled (`EnableSnapshot=true`). The SDK selects the management endpoint for that
cloud automatically. BytePlus defaults to
`https://agentkit.ap-southeast-1.byteplusapi.com` in Singapore.

`InvokeTool`, `AsyncExecCommand`, and `ViewAsyncCommand` use a separate data-plane endpoint: Volcengine uses
`https://agentkit.<region>.volces.com`; the [BytePlus documentation](https://docs.byteplus.com/en/docs/AgentKit/InvokeTool_-_Executes_command_in_a_tool)
specifies `https://agentkit.ap-southeast-1.bytepluses.com` for Singapore,
which differs from the management host `agentkit.ap-southeast-1.byteplusapi.com`.
Both scripts numbered 02 select the invocation endpoint for the cloud and region automatically.
The API version remains `2025-10-30`. A host override is normally unnecessary;
if `BYTEPLUS_AGENTKIT_HOST` or `VOLCENGINE_AGENTKIT_HOST` is set, the selected
host must support the corresponding data-plane actions.

`AGENTKIT_CLOUD_PROVIDER` takes precedence over the compatible `CLOUD_PROVIDER`
variable. When neither is set, the SDK uses its global cloud configuration,
falling back to Volcengine. Legacy `VOLC_ACCESSKEY` / `VOLC_SECRETKEY` credentials
are supported for Volcengine only; BytePlus uses its own `BYTEPLUS_*` credentials.
For temporary credentials, also set `BYTEPLUS_SESSION_TOKEN` or
`VOLCENGINE_SESSION_TOKEN` for the selected cloud.

Optional settings:

- `AGENTKIT_SESSION_TTL_SECONDS`: TTL sent when script 01 creates a session or
  script 05 restores it; defaults to `28800` (8 hours). Script 02 does not send a TTL.
- `AGENTKIT_USER_SESSION_ID`: logical user session ID; script 01 generates one
  when omitted.
- `AGENTKIT_INVOKE_CODE`: Python code executed by script 02; defaults to
  `print('Hello from AgentKit sandbox!')`.
- `AGENTKIT_INVOKE_TIMEOUT_SECONDS`: code execution timeout for script 02;
  defaults to 30 seconds and must be a positive integer.
- `AGENTKIT_INVOKE_KERNEL_NAME`: kernel used by script 02; defaults to `python3`.
- `AGENTKIT_LIFECYCLE_STATE`: shared state JSON path; defaults to
  `.sandbox_snapshot_state.json` in this directory.
- `AGENTKIT_WAIT_TIMEOUT_SECONDS`: timeout for each wait for readiness,
  restoration eligibility, or snapshot deletion; defaults to 600 seconds.
  This does not change the session TTL.
- `AGENTKIT_POLL_INTERVAL_SECONDS`: polling interval; defaults to 5
  seconds.
- `BYTEPLUS_AGENTKIT_REGION` (BytePlus) or `VOLCENGINE_AGENTKIT_REGION`
  (Volcengine): the selected cloud's AgentKit region, taking precedence over the
  generic `AGENTKIT_REGION` override. When neither is set, the SDK resolves the
  region using `BYTEPLUS_REGION` / `VOLCENGINE_REGION`, global configuration,
  and its defaults.
- `BYTEPLUS_AGENTKIT_HOST` or `VOLCENGINE_AGENTKIT_HOST`: optional service host
  override for the selected cloud. Use a hostname without `https://`; normally
  no override is needed. Script 02 also honors this override, so the host must
  support `InvokeTool`; do not use Volcengine's general OpenAPI host or the BytePlus
  management host for it.

When switching clouds or regions, update the tool ID, select a separate state
file with `AGENTKIT_LIFECYCLE_STATE`, and start again from script 01.

## Run code in a session

`02_invoke_session.py` calls [InvokeTool](https://docs.volcengine.com/docs/AgentKit/InvokeTool-Executescommandinatool?lang=zh)
to execute Python code in the sandbox instance recorded in the state file.
Run it after script 01 creates the instance and waits for readiness, or again
after script 05 restores the instance and waits for readiness. The sandbox image
must support the `/v1/jupyter/execute` interface used by `RunCode` and the selected
Python kernel.

The request sends `ToolId`, the saved `instance_id` as `SessionId`,
`OperationType="RunCode"`, and a JSON-string `OperationPayload` containing
`code`, `timeout`, and `kernel_name`. The script explicitly selects the existing
`SessionId` and verifies that the response returns the same instance ID. It does
not use `UserSessionId` to resolve or create an instance. Neither
`AGENTKIT_USER_SESSION_ID` nor `AGENTKIT_SESSION_ID` changes its target.

Run from the repository root, optionally customizing the code:

```bash
export AGENTKIT_INVOKE_CODE="print(sum([1, 2, 3]))"
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/02_invoke_session.py
```

The script saves `invoked_at`, `invoke_response`, and `invoke_result`, parsing
the returned `Result` JSON string for readable output. Standard output is
typically found in `invoke_result.data.outputs`. API errors are reported directly.
Execution results with `success: false` or `data.status: error` cause the script
to exit with an error after saving and printing the result.

SDK 0.8.7 does not provide a dedicated `InvokeTool` method. The script registers
this action and reuses the SDK's signing, credential refresh, and API error
handling without upgrading dependencies.

## Run a Shell command asynchronously

`02_async_invoke_session.py` submits a command through
[AsyncExecCommand](https://docs.volcengine.com/docs/agentkit/AsyncExecCommand_-_Asynchronously_executes_a_Shell_command_in_a_tool?lang=zh),
then repeatedly calls [ViewAsyncCommand](https://docs.volcengine.com/docs/agentkit/ViewAsyncCommand_-_Queries_the_execution_result_of_an_asynchronous_command?lang=zh)
with the returned `TaskId` until completion or a local timeout.
Run after step 01 creates a ready Session, or after step 05 restores the Session and waits for readiness.
The sandbox image must support asynchronous Shell execution through these APIs.
A shared helper registers both actions and reuses SDK 0.8.7 signing and error handling.

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
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/02_async_invoke_session.py
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
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/02_async_invoke_session.py --view-only
```

`--view-only` ignores command/directory settings, submits no new command, and
still updates query results. Running without it submits a new task and replaces
the saved task record; previous remote tasks are not cancelled.

Wait for the asynchronous command to finish before step 03 creates a snapshot.
Step 05 still restores only after the original Session lifecycle ends. Once
restored and ready, run the asynchronous entry again without `--view-only` to
submit a new verification task. Do not assume snapshot restoration restores an
old task execution or query record. Keep Session deletion as the final step.

## Run in order

The default TTL is 8 hours. To shorten the demo, set a shorter TTL **before**
running step 01, for example:

```bash
export AGENTKIT_SESSION_TTL_SECONDS=600
```

Allow enough time for steps 01–04. Changing this variable after creation does
not change the original session's expiry; it only affects subsequent create or
restore requests.

Run steps 01–04 from the repository root to create and invoke the session,
then create and query snapshots:

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/01_create_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/02_invoke_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/03_create_snapshot.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/04_list_and_get_snapshot.py
```

Wait for the original session's TTL to expire and its lifecycle to end before
running step 05. The `session.ExpireAt` field in step 01's output shows the expiry
time when returned by the service:

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/05_restore_from_snapshot.py
```

If step 05 runs too early, the backend returns
`InvalidSnapshot.InstanceAlreadyExists` (the instance is still in use) or
`InvalidSnapshot.InstanceTerminating` (termination is in progress). The script
retries at the polling interval until restoration is allowed or the wait times
out. After a timeout, rerun step 05 once the session lifecycle ends, or increase
`AGENTKIT_WAIT_TIMEOUT_SECONDS`. Other API errors propagate immediately.

After step 05 succeeds, run script 02 again to confirm that the restored instance
can execute code:

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/02_invoke_session.py
```

After verification, delete the snapshot and the restored session in order:

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/06_delete_snapshot.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/07_delete_session.py
```

| Step | Script | Behavior |
| --- | --- | --- |
| 01 | `01_create_session.py` | Create a session, record its instance ID, and wait for readiness. |
| 02 | `02_invoke_session.py` | Execute Python code in the existing session through `InvokeTool`, verify the instance ID, and save the result; run again after restoration. |
| 02 (optional) | `02_async_invoke_session.py` | Submit a Shell command asynchronously and poll; `--view-only` queries the saved task. |
| 03 | `03_create_snapshot.py` | Create a snapshot for the instance, record its ID, and wait for readiness. |
| 04 | `04_list_and_get_snapshot.py` | List all snapshots under the tool with pagination, then get this snapshot's details. |
| 05 | `05_restore_from_snapshot.py` | Restore after the original lifecycle ends with `CreateNewInstance=false`, verify the `SessionId` matches step 01, and wait for readiness. |
| 06 | `06_delete_snapshot.py` | Delete this snapshot and poll the list until it disappears; keep the restored session. |
| 07 | `07_delete_session.py` | Finally delete the session; the service also deletes any remaining snapshots associated with it. |

Step 06 demonstrates snapshot deletion separately; step 07 performs final session
cleanup. For pausing and resuming a running session, see the adjacent
[sandbox_lifecycle](../sandbox_lifecycle/README_en.md) example.

## State file

The eight scripts share `tool_id`, logical user session ID, sandbox instance ID,
and snapshot ID through `.sandbox_snapshot_state.json`. Script 02 also saves
`invoked_at`, `invoke_response`, and `invoke_result`; invoking it again updates
these fields. The default state file
and its temporary file are covered by this directory's `.gitignore`. If you
choose a custom path, ensure that file is excluded from Git as well.

If the state file already records deletion from step 06 or 07, step 05 asks you
to start a new lifecycle from step 01. Cleanup keeps the local state file as an
execution record.

Rerunning step 01 without `AGENTKIT_USER_SESSION_ID` generates a new logical
session ID, creates a new instance, and overwrites the state file. Previously
created instances are not automatically deleted.
