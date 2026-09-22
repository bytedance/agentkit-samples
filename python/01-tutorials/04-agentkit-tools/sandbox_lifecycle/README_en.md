# Sandbox instance (Session) lifecycle scripts

This directory contains five scripts for creating, querying, pausing, resuming,
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

Choose the configuration for the cloud hosting your sandbox. All five scripts
share the same client configuration.

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
The SDK selects the service endpoint for that cloud automatically. BytePlus defaults to
`https://agentkit.ap-southeast-1.byteplusapi.com` in Singapore.

`AGENTKIT_CLOUD_PROVIDER` takes precedence over the compatible `CLOUD_PROVIDER`
variable. When neither is set, the SDK uses its global cloud configuration,
falling back to Volcengine. Legacy `VOLC_ACCESSKEY` / `VOLC_SECRETKEY` credentials
are supported for Volcengine only; BytePlus uses its own `BYTEPLUS_*` credentials.
For temporary credentials, also set `BYTEPLUS_SESSION_TOKEN` or
`VOLCENGINE_SESSION_TOKEN` for the selected cloud.

Optional settings:

- `AGENTKIT_SESSION_TTL_SECONDS`: TTL passed when script 01 creates a session;
  defaults to `28800` (8 hours). Script 04 does not send a TTL when resuming.
- `AGENTKIT_USER_SESSION_ID`: logical session ID used only by script 01, which
  generates one when omitted.
- `AGENTKIT_SESSION_ID`: instance ID used only by script 02; overrides
  the saved `instance_id`.
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
  no override is needed.

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

## Scripts and execution order

The five scripts are:

| Script | Behavior |
| --- | --- |
| `01_create_session.py` | Create a session with an eight-hour default TTL, wait until it is ready, and save the instance ID. |
| `02_list_and_get_session.py` | List all session pages and get the selected instance's details; read-only. |
| `03_pause_session.py` | Pause the saved session, wait for `Paused`, and record `paused_at`. |
| `04_resume_session.py` | Require `paused_at`, resume the same session, verify the instance ID, and wait until it is ready. |
| `05_delete_session.py` | Call `DeleteSession` using the tool ID and saved `instance_id`, then save the response without waiting for backend deletion. |

To verify pause and resume, run **01 → 02 → 03 → 04 → 02**: create and query,
pause and resume, then query the result. Use script 05 for cleanup after this
verification.

Run from the repository root:

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle/01_create_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle/02_list_and_get_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle/03_pause_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle/04_resume_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle/02_list_and_get_session.py
```

Clean up the instance recorded in the state file with this command:

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_lifecycle/05_delete_session.py
```

## State file

The default state file is `.sandbox_state.json` in this directory. It
stores `tool_id`, `user_session_id`, `instance_id`, lifecycle timestamps, and API
responses. Scripts 01, 03, 04, and 05 write state; script 02 only reads it. The
repository's root `.gitignore` ignores this filename. If `AGENTKIT_LIFECYCLE_STATE`
selects a different filename, its ignore behavior depends on the Git rules for
that path.

Scripts 03, 04, and 05 select the instance using the saved `instance_id`; neither
`AGENTKIT_USER_SESSION_ID` nor `AGENTKIT_SESSION_ID` changes their target.

Running script 01 again without `AGENTKIT_USER_SESSION_ID` generates a new
logical session ID, creates a new sandbox instance, and overwrites the state
file. Previously created instances are not automatically deleted.
