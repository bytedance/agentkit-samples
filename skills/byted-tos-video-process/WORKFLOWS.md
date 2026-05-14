# Bytedance TOS Video Process Workflows

This document illustrates common workflows for using the TOS Video Process skill with the Volcengine TOS Python SDK. These examples demonstrate how to combine environment setup, SDK calls, and result handling for practical use cases.

## Table of Contents
- [Workflow 1: Get Video Information](#workflow-1-get-video-information)
- [Workflow 2: Take a Single Snapshot and Save Locally](#workflow-2-take-a-single-snapshot-and-save-locally)
- [Workflow 3: Take a Single Snapshot and Save to TOS](#workflow-3-take-a-single-snapshot-and-save-to-tos)
- [Workflow 4: Batch Snapshotting with a Time Interval](#workflow-4-batch-snapshotting-with-a-time-interval)
- [Workflow 5: Handling Errors](#workflow-5-handling-errors)
- [Workflow 6: Concatenating Video Clips](#workflow-6-concatenating-video-clips)

---

### Prerequisite: Client Initialization

All workflows assume you have a `tos.TosClientV2` instance initialized as shown below. See `README.md` for details on environment variables.

```python
import os
import tos
from tos.exceptions import TosClientError, TosServerError

def create_client() -> tos.TosClientV2:
    """Initializes a TosClientV2 from environment variables."""
    ak = os.getenv('TOS_ACCESS_KEY')
    sk = os.getenv('TOS_SECRET_KEY')
    endpoint = os.getenv('TOS_ENDPOINT')
    region = os.getenv('TOS_REGION')
    security_token = os.getenv('TOS_SECURITY_TOKEN')

    if not all([ak, sk, endpoint, region]):
        raise ValueError("Missing required environment variables for TOS client.")

    return tos.TosClientV2(
        ak=ak,
        sk=sk,
        endpoint=endpoint,
        region=region,
        security_token=security_token,
    )

client = create_client()
bucket_name = os.getenv("TOS_BUCKET")
object_key = os.getenv("TOS_OBJECT_KEY")
```

---

### Workflow 1: Get Video Information

**Goal:** Retrieve the format and stream information for a video file.

**Script:** `scripts/video_info.py`

```bash
python3 scripts/video_info.py --key path/to/video.mp4 --json
```

**Behavior Notes:**
- `--bucket` / `--key` override environment defaults.
- `--json` returns a machine-readable payload with `operation`, `bucket`, `key`, `process`, and `result`.
- Without `--json`, the script prints formatted JSON for interactive use.

---

### Workflow 6: Concatenating Video Clips

**Goal:** Merge multiple video clips stored in TOS into a single output video.

**Script:** `scripts/video_concat.py`

1. **Set Environment**: (Same as Workflow 1)

2. **Execute**:
   ```bash
   python3 scripts/video_concat.py \
     --key clip1.mp4 \
     --fragments "clip2.mp4,clip3.mp4" \
     --saveas-object output/merged.mp4 \
     --wait
   ```

3. **Behavior Notes**:
   - `--key` is the first video clip. `--fragments` specifies additional clips to append, comma-separated.
   - The script submits an async `Concat` job via the TOS gateway's `media_jobs` API.
   - Use `--validate` / `--dry-run` to inspect the resolved payload before submission.
   - Use `--job-id <id>` to query an existing concat job.
   - Use `--json` for machine-readable output.
   - Use `--wait` to poll until the job completes. Without `--wait`, the script returns the created job payload.
   - Default output format is `mp4` with `h264` video codec and `aac` audio codec. Override with `--format`, `--video-codec`, and `--audio-codec`.
   - A single clip (no `--fragments`) effectively re-encodes the input video.

---

### Workflow 2: Take a Single Snapshot and Save Locally

**Goal:** Capture a single frame at a specific timestamp and save it as a local image file.

**Steps:**
1.  Define the snapshot parameters (time, dimensions, format).
2.  Construct the `process` string (e.g., `"video/snapshot,t_10000,w_1280,f_jpg"`).
3.  Call `client.get_object_to_file()` with the `process` string and a local file path.

**Python Example (`scripts/video_snapshot.py`):**
```python
# Assumes 'client', 'bucket_name', 'object_key' are initialized
time_ms = 10000  # Snapshot at 10 seconds
output_filename = f"snapshot_{time_ms}ms.jpg"

process_rule = f"video/snapshot,t_{time_ms},w_1280,f_jpg"

print(f"Requesting snapshot at {time_ms}ms...")
try:
    client.get_object_to_file(
        bucket=bucket_name,
        key=object_key,
        file_path=output_filename,
        process=process_rule
    )
    print(f"Snapshot successfully saved to {output_filename}")
except (TosClientError, TosServerError) as e:
    print(f"An error occurred: {e}")
```

---

### Workflow 3: Take a Single Snapshot and Save to TOS

**Goal:** Capture a single frame and have the TOS server save it directly to another object in the same or a different bucket.

**Script:** `scripts/video_snapshot.py`

```bash
python3 scripts/video_snapshot.py \
  --key path/to/video.mp4 \
  --time 15000 \
  --saveas-bucket my-output-bucket \
  --saveas-object snapshots/frame_15000ms.jpg \
  --json
```

**Behavior Notes:**
- `--saveas-bucket` / `--saveas-object` switch the script into TOS-to-TOS save mode.
- `--dry-run` prints the resolved request without calling TOS.
- `--json` returns a structured payload including save target and TOS response.

---

### Workflow 4: Batch Snapshotting with a Time Interval

**Goal:** Generate multiple snapshots every `N` milliseconds of a video and save them locally or to TOS.

**Script:** `scripts/video_snapshots.py`

**Save to TOS:**
```bash
python3 scripts/video_snapshots.py \
  --key test.mp4 \
  --timestamps 1000 3000 5000 \
  --saveas-bucket my-output-bucket \
  --saveas-object snapshots \
  --json
```

**Generate by interval and save locally:**
```bash
python3 scripts/video_snapshots.py \
  --key test.mp4 \
  --interval-ms 5000 \
  --duration-ms 60000 \
  --output snapshots
```

The shipped script additionally supports:
- `--timestamps 1000 3000 5000` for explicit sampling
- `--interval-ms ... --duration-ms ...` for generated sampling
- `--bucket` / `--key` overrides for easier test execution
- `--output` for local batch save, with `--output-dir` retained as a deprecated alias
- `--saveas-bucket` / `--saveas-object` for TOS persistence
- `--json` for machine-readable output and `--dry-run` for request preview

---

### Workflow 5: Handling Errors

**Goal:** Gracefully handle common errors like invalid credentials, missing files, or server-side issues when using the SDK.

**Error Handling Strategy:**
- Wrap all SDK calls in `try...except` blocks.
- Catch `tos.exceptions.TosServerError` for API errors returned by the TOS service. The exception object contains `.code`, `.status_code`, `.message`, and `.request_id`.
- Catch `tos.exceptions.TosClientError` for client-side issues like network problems or invalid input.
- Check for missing environment variables before initializing the client.

**Python Example:**
```python
# (Assumes 'client' is initialized)
try:
    # An example call that might fail
    response = client.get_object(
        bucket="non-existent-bucket",
        key="non-existent-key",
        process="video/info"
    )
    # ... process successful response
except TosServerError as e:
    print(f"TOS Server Error occurred:")
    print(f"  - Status Code: {e.status_code}")
    print(f"  - Error Code: {e.code}")
    print(f"  - Message: {e.message}")
    print(f"  - Request ID: {e.request_id}")
except TosClientError as e:
    print(f"TOS Client Error: {e.message}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
```
