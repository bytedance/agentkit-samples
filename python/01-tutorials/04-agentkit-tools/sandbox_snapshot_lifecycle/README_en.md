# Sandbox session and snapshot lifecycle scripts

These six scripts demonstrate the sandbox session and snapshot lifecycle
in order. They use the `agentkit.sdk.tools` client from `agentkit-sdk-python` and never store
AK/SK credentials. Signed endpoint `Authorization` query parameters are redacted
before output or state persistence.

The sequence is: **create session → create snapshot → list and get snapshots →
restore after the session lifecycle ends → delete snapshot → delete session**.

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

Choose the configuration for the cloud hosting your sandbox. All six scripts
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

The tool must belong to the selected cloud, account, and region, with snapshots
enabled (`EnableSnapshot=true`). The SDK selects the service endpoint for that
cloud automatically. BytePlus defaults to
`https://agentkit.ap-southeast-1.byteplusapi.com` in Singapore.

`AGENTKIT_CLOUD_PROVIDER` takes precedence over the compatible `CLOUD_PROVIDER`
variable. When neither is set, the SDK uses its global cloud configuration,
falling back to Volcengine. Legacy `VOLC_ACCESSKEY` / `VOLC_SECRETKEY` credentials
are supported for Volcengine only; BytePlus uses its own `BYTEPLUS_*` credentials.
For temporary credentials, also set `BYTEPLUS_SESSION_TOKEN` or
`VOLCENGINE_SESSION_TOKEN` for the selected cloud.

Optional settings:

- `AGENTKIT_SESSION_TTL_SECONDS`: session and restored-instance TTL; defaults to
  `28800` (8 hours).
- `AGENTKIT_USER_SESSION_ID`: logical user session ID; script 01 generates one
  when omitted.
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
  no override is needed.

When switching clouds or regions, update the tool ID, select a separate state
file with `AGENTKIT_LIFECYCLE_STATE`, and start again from script 01.

## Run in order

The default TTL is 8 hours. To shorten the demo, set a shorter TTL **before**
running step 01, for example:

```bash
export AGENTKIT_SESSION_TTL_SECONDS=600
```

Allow enough time for steps 01–03. Changing this variable after creation does
not change the original session's expiry; it only affects subsequent create or
restore requests.

Run steps 01–03 from the repository root to create the session and snapshot,
then query snapshots:

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/01_create_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/02_create_snapshot.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/03_list_and_get_snapshot.py
```

Wait for the original session's TTL to expire and its lifecycle to end before
running step 04. The `session.ExpireAt` field in step 01's output shows the expiry
time when returned by the service:

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/04_restore_from_snapshot.py
```

If step 04 runs too early, the backend returns
`InvalidSnapshot.InstanceAlreadyExists` (the instance is still in use) or
`InvalidSnapshot.InstanceTerminating` (termination is in progress). The script
retries at the polling interval until restoration is allowed or the wait times
out. After a timeout, rerun step 04 once the session lifecycle ends, or increase
`AGENTKIT_WAIT_TIMEOUT_SECONDS`. Other API errors propagate immediately.

After step 04 succeeds, delete the snapshot and the restored session in order:

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/05_delete_snapshot.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/06_delete_session.py
```

| Step | Script | Behavior |
| --- | --- | --- |
| 01 | `01_create_session.py` | Create a session, record its instance ID, and wait for readiness. |
| 02 | `02_create_snapshot.py` | Create a snapshot for the instance, record its ID, and wait for readiness. |
| 03 | `03_list_and_get_snapshot.py` | List all snapshots under the tool with pagination, then get this snapshot's details. |
| 04 | `04_restore_from_snapshot.py` | Restore after the original lifecycle ends with `CreateNewInstance=false`, verify the `SessionId` matches step 01, and wait for readiness. |
| 05 | `05_delete_snapshot.py` | Delete this snapshot and poll the list until it disappears; keep the restored session. |
| 06 | `06_delete_session.py` | Finally delete the session; the service also deletes any remaining snapshots associated with it. |

Step 05 demonstrates snapshot deletion separately; step 06 performs final session
cleanup. For pausing and resuming a running session, see the adjacent
[sandbox_lifecycle](../sandbox_lifecycle/README_en.md) example.

## State file

The six scripts share `tool_id`, logical user session ID, sandbox instance ID,
and snapshot ID through `.sandbox_snapshot_state.json`. The default state file
and its temporary file are covered by this directory's `.gitignore`. If you
choose a custom path, ensure that file is excluded from Git as well.

If the state file already records deletion from step 05 or 06, step 04 asks you
to start a new lifecycle from step 01. Cleanup keeps the local state file as an
execution record.

Rerunning step 01 without `AGENTKIT_USER_SESSION_ID` generates a new logical
session ID, creates a new instance, and overwrites the state file. Previously
created instances are not automatically deleted.
