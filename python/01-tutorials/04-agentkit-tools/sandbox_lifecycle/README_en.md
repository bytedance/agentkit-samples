# Sandbox instance (Session) lifecycle scripts

This directory contains six scripts for creating, querying, invoking, pausing, resuming,
and deleting sessions. `02_list_and_get_session.py` is read-only.
They use the AgentKit SDK's `agentkit.sdk.tools` client and
never store AK/SK credentials. Signed endpoint `Authorization` query parameters
are redacted before output or state persistence.

`PauseSession` / `ResumeSession` pause and resume the same Session.

For Chinese instructions, see [README.md](README.md).

## Install dependencies

Python 3.10 or later is required. This example pins `agentkit-sdk-python==0.8.7`,
which includes `PauseSession` / `ResumeSession`. Install from the repository root:

```bash
pip install -r python/01-tutorials/04-agentkit-tools/sandbox_lifecycle/requirements.txt
```

## Environment

Choose the configuration for the cloud hosting your sandbox. All six scripts
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

The tool must belong to the selected cloud, account, and region.
The SDK selects the management endpoint for that cloud automatically. BytePlus defaults to
`https://agentkit.ap-southeast-1.byteplusapi.com` in Singapore.

`InvokeTool` uses a separate data-plane endpoint: Volcengine uses
`https://agentkit.<region>.volces.com`; the [BytePlus documentation](https://docs.byteplus.com/en/docs/AgentKit/InvokeTool_-_Executes_command_in_a_tool)
specifies `https://agentkit.ap-southeast-1.bytepluses.com` for Singapore,
which differs from the management host `agentkit.ap-southeast-1.byteplusapi.com`.
Script 03 selects the invocation endpoint for the cloud and region automatically.
The API version remains `2025-10-30`. A host override is normally unnecessary;
if `BYTEPLUS_AGENTKIT_HOST` or `VOLCENGINE_AGENTKIT_HOST` is set, the selected
host must support `InvokeTool`.

`AGENTKIT_CLOUD_PROVIDER` takes precedence over the compatible `CLOUD_PROVIDER`
variable. When neither is set, the SDK uses its global cloud configuration,
falling back to Volcengine. Legacy `VOLC_ACCESSKEY` / `VOLC_SECRETKEY` credentials
are supported for Volcengine only; BytePlus uses its own `BYTEPLUS_*` credentials.
For temporary credentials, also set `BYTEPLUS_SESSION_TOKEN` or
`VOLCENGINE_SESSION_TOKEN` for the selected cloud.

Optional settings:

- `AGENTKIT_SESSION_TTL_SECONDS`: TTL passed when script 01 creates a session;
  defaults to `28800` (8 hours). Scripts 03 and 05 do not send a TTL when invoking
  or resuming the session.
- `AGENTKIT_USER_SESSION_ID`: logical session ID used only by script 01, which
  generates one when omitted.
- `AGENTKIT_SESSION_ID`: instance ID used only by script 02; overrides
  the saved `instance_id`.
- `AGENTKIT_INVOKE_CODE`: Python code executed by script 03; defaults to
  `print('Hello from AgentKit sandbox!')`.
- `AGENTKIT_INVOKE_TIMEOUT_SECONDS`: code execution timeout for script 03;
  defaults to 30 seconds and must be a positive integer.
- `AGENTKIT_INVOKE_KERNEL_NAME`: kernel used by script 03; defaults to `python3`.
- `AGENTKIT_SANDBOX_TOOL_ID`: compatible alias for `AGENTKIT_TOOL_ID`; if both
  are set, they must match.
- `AGENTKIT_LIFECYCLE_STATE`: shared state JSON path; defaults to
  `.sandbox_state.json` in the script directory, regardless of the
  working directory. The query script only reads this file.
- `AGENTKIT_WAIT_TIMEOUT_SECONDS`: timeout for create, pause, and resume state
  polling; defaults to 600 seconds. The delete script does not poll for deletion.
- `AGENTKIT_POLL_INTERVAL_SECONDS`: readiness polling interval; defaults to 5
  seconds.
- `BYTEPLUS_AGENTKIT_REGION` (BytePlus) or `VOLCENGINE_AGENTKIT_REGION`
  (Volcengine): the selected cloud's AgentKit region, taking precedence over the
  generic `AGENTKIT_REGION` override. When neither is set, the SDK resolves the
  region using `BYTEPLUS_REGION` / `VOLCENGINE_REGION`, global configuration,
  and its defaults.
- `BYTEPLUS_AGENTKIT_HOST` or `VOLCENGINE_AGENTKIT_HOST`: optional service host
  override for the selected cloud. Use a hostname without `https://`; normally
  no override is needed. Script 03 also honors this override, so the host must
  support `InvokeTool`; do not use Volcengine's general OpenAPI host or the BytePlus
  management host for it.

When switching clouds or regions, update the tool ID and select a separate state
file with `AGENTKIT_LIFECYCLE_STATE`. Start lifecycle operations from script 01;
querying an existing session does not require creating a new instance.

## List sessions and get session details

`02_list_and_get_session.py` follows `ListSessions` pagination to list all sessions
under the tool, then calls `GetSession` for the selected instance. It only reads
cloud resources and local state; it does not update the state file.

Run from the repository root:

```bash
pip install -r python/01-tutorials/04-agentkit-tools/sandbox_lifecycle/requirements.txt
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle/02_list_and_get_session.py
```

By default, the script uses `tool_id` and `instance_id` from this directory's
state file, or the file selected by `AGENTKIT_LIFECYCLE_STATE`. Run it after
creating, pausing, or resuming a session.

You can also select an existing session without running the create script:

```bash
export AGENTKIT_TOOL_ID=t-xxxxxxxx
export AGENTKIT_SESSION_ID="<SessionId>"
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle/02_list_and_get_session.py
```

`AGENTKIT_SESSION_ID` overrides the saved `instance_id`. Use the instance's API
`SessionId`, not its logical `UserSessionId`. The existing consistency check
between the environment and saved tool ID still applies. When neither an
explicit nor a saved instance ID is available, the script only lists sessions
and outputs `session: null`. Empty lists are valid; `GetSession` API errors are
reported directly. Signed endpoints in both the list and details are redacted.

## Run code in a session

`03_invoke_session.py` calls [InvokeTool](https://docs.volcengine.com/docs/AgentKit/InvokeTool-Executescommandinatool?lang=zh)
to execute Python code in the sandbox instance recorded in the state file.
Create the instance with script 01 first and ensure it is ready. If it is paused,
run script 05 to resume it before invoking script 03. The sandbox image must
support the `/v1/jupyter/execute` interface used by `RunCode` and the selected
Python kernel.

The request sends `ToolId`, the saved `instance_id` as `SessionId`,
`OperationType="RunCode"`, and a JSON-string `OperationPayload` containing
`code`, `timeout`, and `kernel_name`. The script explicitly selects the existing
`SessionId` and verifies that the response returns the same instance ID. It does
not use `UserSessionId` to resolve or create an instance.

Run from the repository root, optionally customizing the code:

```bash
export AGENTKIT_INVOKE_CODE="print(sum([1, 2, 3]))"
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle/03_invoke_session.py
```

The script saves `invoked_at`, `invoke_response`, and `invoke_result`, parsing
the returned `Result` JSON string for readable output. Standard output is
typically found in `invoke_result.data.outputs`. API errors are reported directly.
Execution results with `success: false` or `data.status: error` cause the script
to exit with an error after saving and printing the result.

SDK 0.8.7 does not provide a dedicated `InvokeTool` method. The script registers
this action and reuses the SDK's signing, credential refresh, and API error
handling without upgrading dependencies.

## Scripts and execution order

The six scripts are:

| Script | Behavior |
| --- | --- |
| `01_create_session.py` | Create a session with an eight-hour default TTL, wait until it is ready, and save the instance ID. |
| `02_list_and_get_session.py` | List all session pages and get the selected instance's details; read-only. |
| `03_invoke_session.py` | Execute Python code in the existing session through `InvokeTool`, verify the instance ID, and save the result. |
| `04_pause_session.py` | Pause the saved session, wait for `Paused`, and record `paused_at`. |
| `05_resume_session.py` | Require `paused_at`, resume the same session, verify the instance ID, and wait until it is ready. |
| `06_delete_session.py` | Call `DeleteSession` using the tool ID and saved `instance_id`, then save the response without waiting for backend deletion. |

To verify invocation, pause, and resume, run **01 → 02 → 03 → 04 → 05 → 02 → 03**:
create, query, and invoke the session, pause and resume it, then query and invoke
the resumed instance again. Use script 06 for cleanup after this verification.

Run from the repository root:

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle/01_create_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle/02_list_and_get_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle/03_invoke_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle/04_pause_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle/05_resume_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle/02_list_and_get_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle/03_invoke_session.py
```

Clean up the instance recorded in the state file with this command:

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle/06_delete_session.py
```

## State file

The default state file is `.sandbox_state.json` in this directory. It
stores `tool_id`, `user_session_id`, `instance_id`, lifecycle timestamps, and API
responses. Scripts 01, 03, 04, 05, and 06 write state; script 02 only reads it. The
repository's root `.gitignore` ignores this filename. If `AGENTKIT_LIFECYCLE_STATE`
selects a different filename, its ignore behavior depends on the Git rules for
that path.

Scripts 03, 04, 05, and 06 select the instance using the saved `instance_id`; neither
`AGENTKIT_USER_SESSION_ID` nor `AGENTKIT_SESSION_ID` changes their target.

Running script 01 again without `AGENTKIT_USER_SESSION_ID` generates a new
logical session ID, creates a new sandbox instance, and overwrites the state
file. Previously created instances are not automatically deleted.
