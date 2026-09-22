# Sandbox Session and Snapshot Lifecycle HTTP Example

This directory provides sandbox session and snapshot lifecycle scripts that do
not depend on `agentkit.sdk`. The scripts call the AgentKit Tools OpenAPI
directly. `_http_client.py` implements HTTP requests, HMAC-SHA256 request
signing, error parsing, and basic retries locally in this example.

This example is parallel to the SDK-based `../sandbox_snapshot_lifecycle`
example. It keeps the same execution order and state-file behavior. Signed
endpoint `Authorization` query parameters are redacted before output or state
persistence.

`PauseSession` / `ResumeSession` pause and resume the same Session.
`ResumeSessionFromSnapshot` restores an instance from a snapshot and is a
different API.

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

## Lifecycle Settings

- `AGENTKIT_SESSION_TTL_SECONDS`: session and restored-instance TTL; defaults to
  `28800` seconds (8 hours).
- `AGENTKIT_USER_SESSION_ID`: logical user session ID; script 01 generates one
  when omitted.
- `AGENTKIT_LIFECYCLE_STATE`: shared state JSON path; defaults to
  `.sandbox_snapshot_state.json` in this directory.
- `AGENTKIT_WAIT_TIMEOUT_SECONDS`: readiness timeout; defaults to 600 seconds.
- `AGENTKIT_POLL_INTERVAL_SECONDS`: readiness polling interval; defaults to 5
  seconds.
- `AGENTKIT_HTTP_TIMEOUT_SECONDS`: per-request HTTP timeout; defaults to 30
  seconds.
- `AGENTKIT_HTTP_RETRIES`: retry count for connection errors, HTTP 429, and HTTP
  503; defaults to 2.

## Run In Order

Run these commands from the repository root:

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/01_create_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/02_create_snapshot.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/03_list_and_get_snapshot.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/04_delete_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/05_restore_from_snapshot.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/06_delete_snapshot.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/07_pause_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle_http/08_resume_session.py
```

Script purposes:

1. `01_create_session.py`: checks that the Tool has snapshots enabled, creates a
   Session, and waits until the sandbox instance becomes `Ready`.
2. `02_create_snapshot.py`: creates a snapshot for the Session's sandbox
   instance and waits until the snapshot becomes `Ready`.
3. `03_list_and_get_snapshot.py`: lists all snapshots under the Tool with
   pagination, then gets the newly created snapshot.
4. `04_delete_session.py`: deletes the Session's sandbox instance while keeping
   the snapshot.
5. `05_restore_from_snapshot.py`: sends `CreateNewInstance=false` to restore the
   original sandbox from the snapshot and verifies that the returned `SessionId`
   matches script 01. If the instance is still terminating asynchronously, the
   script waits and retries.
6. `06_delete_snapshot.py`: deletes the recorded snapshot, follows pagination,
   and waits until that snapshot no longer appears under the Tool. It does not
   delete the sandbox instance restored by script 05.
7. `07_pause_session.py`: pauses the Session recorded in the state file and
   polls `GetSession` until its status becomes `Paused`. It can also run
   directly after script 01.
8. `08_resume_session.py`: resumes the same Session, verifies that the instance
   ID is unchanged, and waits until the Session becomes `Ready` again.

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
logical user session ID, sandbox instance ID, and snapshot ID. This file is
ignored by the `.gitignore` in this directory.

If you rerun script 01 without `AGENTKIT_USER_SESSION_ID`, it generates a new
logical session ID, creates a new sandbox instance, and overwrites the state
file. Previously created instances are not deleted automatically.
