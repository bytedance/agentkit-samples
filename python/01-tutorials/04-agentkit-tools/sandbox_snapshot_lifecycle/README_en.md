# Sandbox session and snapshot lifecycle scripts

These eight scripts exercise the complete sandbox session and snapshot lifecycle
in order. They use the repository's `agentkit.sdk.tools` client and never store
AK/SK credentials. Signed endpoint `Authorization` query parameters are redacted
before output or state persistence.

`PauseSession` / `ResumeSession` pause and resume the same Session.
`ResumeSessionFromSnapshot` restores an instance from a snapshot and is a
different API.

## Install dependencies

The two Session APIs are available in `agentkit-sdk-python==0.8.7`:

```bash
pip install -r python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/requirements.txt
```

## Environment

The SDK reads BytePlus credentials from `BYTEPLUS_ACCESS_KEY` and
`BYTEPLUS_SECRET_KEY` (the legacy `VOLC_ACCESSKEY` and `VOLC_SECRETKEY` names
also work).

```bash
export AGENTKIT_TOOL_ID=t-xxxxxxxx
```

Optional settings:

- `AGENTKIT_SESSION_TTL_SECONDS`: session and restored-instance TTL; defaults to
  `28800` (8 hours).
- `AGENTKIT_USER_SESSION_ID`: logical user session ID; script 01 generates one
  when omitted.
- `AGENTKIT_LIFECYCLE_STATE`: shared state JSON path; defaults to
  `.sandbox_snapshot_state.json` in this directory.
- `AGENTKIT_WAIT_TIMEOUT_SECONDS`: readiness timeout; defaults to 600 seconds.
- `AGENTKIT_POLL_INTERVAL_SECONDS`: readiness polling interval; defaults to 5
  seconds.
- `VOLCENGINE_AGENTKIT_REGION` or `AGENTKIT_REGION`: explicit region override;
  otherwise the SDK's normal region resolution is used.

## Run in order

Run these commands from the repository root:

```bash
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/01_create_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/02_create_snapshot.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/03_list_and_get_snapshot.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/04_delete_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/05_restore_from_snapshot.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/06_delete_snapshot.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/07_pause_session.py
python python/01-tutorials/04-agentkit-tools/sandbox_snapshot_lifecycle/08_resume_session.py
```

Script 05 sends `CreateNewInstance=false`. This asks the backend to restore the
original sandbox instance instead of allocating a new ID. The script also
compares the returned `SessionId` with the ID saved by script 01 and fails if
they differ.

Script 06 deletes the recorded snapshot, follows snapshot-list pagination, and
waits until that snapshot no longer appears under the tool. It does not delete
the sandbox instance restored by script 05.

Script 07 calls `PauseSession` for the Session recorded in the state file and
polls `GetSession` until its status becomes `Paused`. It can also run directly
after script 01.

Script 08 calls `ResumeSession` for the same Session, verifies that the returned
instance ID is unchanged, and waits until the Session becomes `Ready` again.
