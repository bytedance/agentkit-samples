# Bytedance TOS Video Process SDK Reference

This document provides a detailed reference for the parameters and return values of the core video processing operations, as implemented via the Volcengine TOS Python SDK.

## Table of Contents
- [Authentication](#authentication)
- [Core Operations](#core-operations)
  - [1. `videoInfo`](#1-videoinfo)
  - [2. `videoSnapshot`](#2-videosnapshot)
  - [3. `videoSnapshots`](#3-videosnapshots)
  - [4. `videoConcat`](#4-videoconcat)
- [Data Models](#data-models)
  - [VideoInfo Object](#videoinfo-object)
  - [SnapshotSaveResult Object](#snapshotsaveresult-object)

---

## Authentication

Authentication is handled automatically by the `tos.TosClientV2` client during initialization. Credentials should be provided via environment variables as described in the `README.md`. The SDK will construct the necessary request headers.

---

## Core Operations

Video processing is invoked by passing a specially formatted `process` string to the `get_object` or `get_object_to_file` methods of the TOS SDK client.

### 1. `videoInfo`

Retrieves metadata for a specified video object in TOS.

**SDK Method:** `client.get_object()`

**Key Parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `bucket` | string | Yes | The name of the bucket containing the video. |
| `key` | string | Yes | The full object key (path) of the video file. |
| `process` | string | Yes | Must be set to the exact string `"video/info"`. |

**Example:**

```python
import tos
import json

# client = initialized tos.TosClientV2
# bucket_name = "your-bucket"
# object_key = "your-video.mp4"

try:
    response = client.get_object(
        bucket=bucket_name,
        key=object_key,
        process="video/info"
    )
    # The response body is a stream, read it to get the content
    raw_data = response.read()
    video_info = json.loads(raw_data.decode('utf-8'))
    print(video_info)
except tos.exceptions.TosServerError as e:
    print(f"Failed to get video info: {e}")

```

**Success Response:**
- The `response.read()` call returns a `bytes` object containing a JSON string.
- This JSON string represents the [VideoInfo Object](#videoinfo-object).

---

### 2. `videoSnapshot`

Captures a single frame from a video. The output can be either saved to a local file, returned as a data stream, or persisted directly within TOS.

#### Mode 1: Save to a Local File

**SDK Method:** `client.get_object_to_file()`

| Parameter | Type | Required | Description |
|---|---|---|---|
| `bucket` | string | Yes | The bucket where the video is located. |
| `key` | string | Yes | The object key of the video file. |
| `file_path` | string | Yes | The local path where the snapshot image will be saved. |
| `process` | string | Yes | A composite string starting with `video/snapshot`. See below. |

#### Mode 2: Save directly to TOS

**SDK Method:** `client.get_object()`

| Parameter | Type | Required | Description |
|---|---|---|---|
| `bucket` | string | Yes | The source bucket of the video. |
| `key` | string | Yes | The source object key of the video. |
| `process` | string | Yes | A composite string starting with `video/snapshot`. See below. |
| `save_bucket` | string | Yes | The destination bucket to save the snapshot in. |
| `save_object` | string | Yes | The destination object key for the saved snapshot. |

#### Constructing the `process` Parameter

The `process` string for `videoSnapshot` is built as `video/snapshot` followed by a comma-separated list of `key_value` options.

| Option | SDK Equivalent | Description |
|---|---|---|
| `t` | `time` (int) | Timestamp in **milliseconds (ms)** to capture the frame. |
| `w` | `width` (int) | Width of the snapshot in pixels. If `0`, aspect ratio is maintained. |
| `h` | `height` (int) | Height of the snapshot in pixels. If `0`, aspect ratio is maintained. |
| `m` | `mode` (string) | `fast` captures the nearest keyframe before `time`. Default is precise. |
| `f` | `output_format` (string) | `jpg` (default) or `png`. |
| `ar`| `auto_rotate` (string) | `auto`: rotate automatically. `w`: force landscape. `h`: force portrait. |

**Example `process` string:** `"video/snapshot,t_5000,w_1280,f_jpg"`

**Example (Save to Local File):**

```python
# Captures frame at 10s and saves to "frame.jpg"
client.get_object_to_file(
    bucket=bucket_name,
    key=object_key,
    file_path="frame.jpg",
    process="video/snapshot,t_10000"
)
```

**Example (Save to TOS):**

```python
response = client.get_object(
    bucket=bucket_name,
    key=object_key,
    process="video/snapshot,t_10000",
    save_bucket="my-results-bucket",
    save_object="snapshots/frame_at_10s.jpg"
)
# response.read() will contain a JSON string with the save result
save_result = json.loads(response.read().decode('utf-8'))
print(save_result)
```

**Success Response (Save to TOS):**
- The `response.read()` call returns a `bytes` object containing a JSON string.
- This JSON string represents the [SnapshotSaveResult Object](#snapshotsaveresult-object).

---

### 3. `videoSnapshots`

This is not a single SDK method but a client-side orchestration pattern. It involves making multiple `videoSnapshot` calls in a loop or in parallel. The `scripts/video_snapshots.py` script provides a complete, concurrent implementation.

**Functionality:**
- Iterates through a list of user-provided or calculated timestamps.
- For each timestamp, it makes a `get_object_to_file` or `get_object` (with `save_bucket`/`save_object`) request.
- It can either save the resulting images locally or save them back to TOS.
- It supports both explicit timestamps and interval-derived timestamps.
- The current script also accepts `--bucket` and `--key` overrides instead of relying only on environment variables.

Please refer to the `scripts/video_snapshots.py` for a reference implementation.

---

### 4. `videoConcat`

Concatenates multiple video clips into a single output video. This is an async operation submitted via the TOS gateway's `media_jobs` API.

**API Endpoint:** `POST /{bucket}?media_jobs=&job_type=Concat`

**Job Payload:**

```json
{
  "Input": {
    "Object": "clip1.mp4"
  },
  "ConcatConfig": {
    "ConcatFragments": [
      {"Object": "clip2.mp4"},
      {"Object": "clip3.mp4"}
    ],
    "Container": {
      "Format": "mp4"
    },
    "Video": {
      "Codec": "h264"
    },
    "Audio": {
      "Codec": "aac"
    }
  },
  "Output": {
    "Region": "cn-beijing",
    "Bucket": "your-bucket",
    "Object": "output/merged.mp4"
  }
}
```

**CLI Mapping:**

| CLI argument | Meaning | Notes |
|---|---|---|
| `--key` | First video clip object key | Required |
| `--fragments` | Additional clips, comma-separated | Optional |
| `--format` | Output container format | Default `mp4` |
| `--video-codec` | Video codec | Default `h264` |
| `--audio-codec` | Audio codec | Default `aac` |
| `--output-key` | Output object key | Default `<key>_concat.<format>` |
| `--output-bucket` | Output bucket | Default same as source |
| `--wait` | Poll until completion | Optional |
| `--timeout` | Max wait time in seconds | Default `600` |

**Script:** `scripts/video_concat.py`

---

## Data Models

### VideoInfo Object

A JSON object containing detailed information about the video's format and streams, as returned by the `video/info` process.

| Field | Type | Description |
|---|---|---|
| `Format` | object | Container format details (e.g., mov, mp4). Includes `Duration`, `Size`, `BitRate`. |
| `VideoStream` | object | Video stream details. Includes `Width`, `Height`, `CodecName`, `Duration`, `AvgFrameRate`. |
| `AudioStream`| object | (Optional) Audio stream details if present. Includes `CodecName`, `SampleRate`, `Channels`. |

**Example Snippet:**
```json
{
  "VideoStream": {
    "Width": 1920,
    "Height": 1080,
    "Duration": "10.000000",
    "AvgFrameRate": "25/1"
  },
  "Format": {
    "FormatName": "mov,mp4,m4a,3gp,3g2,mj2",
    "Duration": "10.024000",
    "Size": "2506000"
  }
}
```

### SnapshotSaveResult Object

A JSON object returned when a snapshot is successfully saved to TOS using the `save_bucket` and `save_object` parameters.

| Field | Type | Description |
|---|---|---|
| `ETag` | string | The ETag of the saved snapshot object. |
| `Bucket` | string | The bucket where the snapshot was saved. |
| `Object` | string | The object key of the saved snapshot. |
| `VersionId` | string | The version ID of the saved object if versioning is enabled. |
| `HashCrc64ecma` | string | The CRC64 checksum of the object. |
