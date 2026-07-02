---
name: byted-byteplus-vod-frame-extraction
description: "Upload video/audio media to BytePlus VOD (Video on Demand) storage, returning the Vid and playback references; supports local file upload (ApplyUploadInfo + TOS + CommitUploadInfo) and URL pull upload (UploadMediaByUrl); also submits frame extraction jobs on ingested media (StartExecution / Operation.Task.Snapshot), including specified time, fixed interval, specified frame, scene-change, sprite image, and output index modes. Trigger keywords: VOD frame extraction, frame extraction, extract frames, video snapshot, thumbnail, screenshot from video, StartExecution Snapshot."
version: 1.0.0
license: Apache-2.0
env:
  - name: BYTEPLUS_ACCESSKEY
    description: BytePlus Access Key
    required: true
    secret: true
    default: ''
  - name: BYTEPLUS_SECRETKEY
    description: BytePlus Secret Key
    required: true
    secret: true
    default: ''
  - name: VOD_SPACE_NAME
    description: VOD space name
    required: true
    secret: false
    default: ''
---

# VOD frame extraction

Uploads video/audio to a BytePlus VOD space (from a **local file** or a **public URL**) and returns a `vid://...` reference. For media already in VOD, submits **Snapshot** tasks (`StartExecution` -> `Operation.Task.Type: Snapshot`) for frame extraction.

---

## Product scope

| Aspect | Behaviour |
|--------|-----------|
| **Input** | `Vid` or `DirectUrl` (JSON field `video`) |
| **Extraction strategy** | Default: specified time at 0 ms. Supported: specified time, fixed interval, specified frames, scene-change detection. |
| **Target image size** | Default `resolution: 720p` because the API Snapshot Target requires a resolution. Optional `scale_long` / `scale_short`. |
| **Sprite image** | Optional `sprite` / `sprite_config`. |
| **Output index mode** | Optional `output_mode`: `Files` or `Index`. |
| **Advanced API fields** | Use `snapshot` for complete passthrough or `snapshot_options` to deep-merge extra fields into generated `Snapshot`. |

If the user does not specify a strategy, use **specified time at 0 ms**. If they ask for multiple thumbnails but do not provide times, ask for the timestamps or use fixed interval only when they explicitly request evenly-spaced extraction.

---

## Prerequisites

- **Environment variables** (required; optionally place a `.env` in the working directory — scripts load it automatically):
  - `BYTEPLUS_ACCESSKEY` — BytePlus Access Key
  - `BYTEPLUS_SECRETKEY` — BytePlus Secret Key
  - `VOD_SPACE_NAME` — VOD space name
- **Environment template:** see `scripts/env.md`.
- **Execution:** examples use `uv run python ...` (`python scripts/...` works if deps are installed).

---

## Workflow overview

```text
Upload pipeline (local file):
  [S1_APPLY]  ApplyUploadInfo -> TOS upload address + SessionKey
  [S2_TOS]    PUT file to TOS (direct or chunked)
  [S3_COMMIT] CommitUploadInfo -> Vid
  Output: { Vid, Source, PlayURL, FileName, SpaceName, SourceUrl }

Upload pipeline (URL):
  [S1_UPLOAD] Submit URL upload job (UploadMediaByUrl) -> JobId
  [S2_POLL]   Poll QueryUploadTaskInfo -> Vid
  Output: { Vid, Source, PlayURL, FileName, SpaceName, SourceUrl, JobId }

Snapshot pipeline:
  [S3_SNAPSHOT] Submit frame extraction task (StartExecution / Task.Type Snapshot) -> RunId
  [S4_POLL]     Poll GetExecution -> output snapshot files / raw Snapshot output
  Output: { Status, SpaceName, ImageUrls[], Snapshot }
```

---

## Quick self-check

Before running any script:

- `.env` or env vars contain `BYTEPLUS_ACCESSKEY`, `BYTEPLUS_SECRETKEY`, and `VOD_SPACE_NAME`.

Pick the pipeline from user intent:

| User intent | Pipeline | Entry script |
|-------------|----------|--------------|
| Upload video to VOD | Upload | `scripts/upload.py` |
| Extract frames / thumbnails | Frame extraction | `scripts/snapshot.py` |

---

## S1_UPLOAD & S2_POLL: upload and obtain Vid

Run from the Skill root directory (`byted-byteplus-vod-frame-extraction/`):

```bash
uv run python scripts/upload.py "/path/to/video.mp4" [space_name]
uv run python scripts/upload.py "https://example.com/video.mp4" [space_name]
```

- First argument: **local file path** or public `http://` / `https://` URL.
- Second argument (optional): space name; if omitted, `VOD_SPACE_NAME` is used.
- Paths and URLs **must include a file extension**.

On success, preserve `Source` (`vid://...`) for downstream processing.

---

## S3_SNAPSHOT & S4_POLL: frame extraction

Run from the Skill root directory (`byted-byteplus-vod-frame-extraction/`):

```bash
# Default: first frame at 0 ms, 720p
uv run python scripts/snapshot.py '{"type":"Vid","video":"v0310abc"}'

# Three exact timestamps in milliseconds
uv run python scripts/snapshot.py '{"type":"Vid","video":"vid://v0d225gxxx","strategy":"specified_time","times":[0,5000,10000],"resolution":"720p"}' production_space

# Every 3 seconds
uv run python scripts/snapshot.py '{"type":"Vid","video":"v0310abc","strategy":"interval","interval_ms":3000}'

# Scene-change snapshots
uv run python scripts/snapshot.py '{"type":"Vid","video":"v0310abc","strategy":"scene_change","threshold":0.1}'

uv run python scripts/snapshot.py @params.json

# Resume after timeout
uv run python scripts/poll_execution.py '<RunId>' [space_name]
```

### Parameter reference

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `type` | string | no | `Vid` or `DirectUrl`. Default `Vid`. |
| `video` | string | yes | Vid or VOD `FileName`; `vid://` / `directurl://` prefixes are stripped automatically. |
| `strategy` | string/object | no | `specified_time`, `interval`, `specified_frames`, or `scene_change`. Default `specified_time`. If object, used directly as API `Strategy`. |
| `times` | integer/array | no | Millisecond offsets for `specified_time`. Default `[0]`. |
| `interval_ms` | integer | for interval | Millisecond interval for fixed interval snapshots. |
| `frames` | integer array | for specified frames | Frame indexes for `specified_frames`; `0` means first frame and `-1` means last frame. |
| `threshold` | float | no | Scene-change threshold in `[0, 1]`, default `0.1`. |
| `resolution` | string | no | Default `720p`. Allowed: `240p`, `360p`, `480p`, `720p`, `1080p`. |
| `scale_long` / `scale_short` | integer | no | Long/short output image edge, [0, 4096]. |
| `sprite` / `sprite_config` | boolean/object | no | Sprite image config. Object is passed directly as `SpriteConfig`. |
| `output_mode` | string | no | `Files` or `Index`, maps to `IndexOption.Mode`. |
| `snapshot` | object | no | Complete API `Snapshot` object passthrough. |
| `snapshot_options` | object | no | Advanced fields deep-merged into generated `Snapshot`. |

### Agent prompting

Ask for timestamps, interval, frame numbers, or scene-change detection only when the user's intent is ambiguous. Use conversational wording: “which frames or timestamps should I extract?” rather than raw API field names. If the user asks for a simple cover/thumbnail, use the default first-frame snapshot.

### Output format

On success, one JSON object is printed to stdout:

```json
{
  "Status": "Success",
  "SpaceName": "my_space",
  "ImageUrls": [
    {
      "FileId": "...",
      "Vid": "",
      "DirectUrl": "path/to/snapshot.jpg",
      "Source": "directurl://path/to/snapshot.jpg",
      "Url": "https://example.cdn.com/...",
      "Raw": {}
    }
  ],
  "VideoUrls": [],
  "AudioUrls": [],
  "Texts": [],
  "Snapshot": {}
}
```

- `ImageUrls[].Url`: playable / downloadable when signing succeeds for the space.
- `Snapshot`: raw API output from `Output.Task.Snapshot`.

### Timeout handling

```json
{
  "error": "Polling timed out (360 attempts × 5s); the job is still processing",
  "resume_hint": {
    "description": "The job has not finished yet; resume polling with the command below",
    "command": "uv run python scripts/poll_execution.py '<RunId>' [space_name]"
  }
}
```

---

## Environment variables

| Name | Description | Required |
|------|-------------|----------|
| `BYTEPLUS_ACCESSKEY` | BytePlus Access Key | Yes |
| `BYTEPLUS_SECRETKEY` | BytePlus Secret Key | Yes |
| `VOD_SPACE_NAME` | VOD space name | Yes (or via CLI argument) |
| `VOD_POLL_INTERVAL` | Polling interval (seconds, default 5) | No |
| `VOD_POLL_MAX` | Maximum polling attempts (default 360) | No |
| `VOD_URL_EXPIRE_MINUTES` | Signed URL expiry (minutes, default 60) | No |
| `VOD_PLAY_DOMAIN` | Force a specific playback domain (optional, highest priority) | No |
| `VOD_HOST` | Override VOD OpenAPI hostname (optional) | No |
| `TOS_UPLOAD_CONNECT_TIMEOUT` | TOS upload connect timeout in seconds (default 5) | No |
| `TOS_UPLOAD_READ_TIMEOUT` | TOS upload read timeout in seconds (default 600) | No |

---

## References

- [StartExecution / OperationTaskSnapshot](https://docs.byteplus.com/en/docs/byteplus-vod/reference-startexecution#operationtasksnapshot)
- [snapshot parameter reference](references/snapshot.md)
- API: `ApplyUploadInfo` (`2023-01-01`)
- API: `CommitUploadInfo` (`2023-01-01`)
- API: `UploadMediaByUrl` (`2023-01-01`)
- API: `QueryUploadTaskInfo` (`2023-01-01`)
- API: `StartExecution` (`2025-07-01`)
- API: `GetExecution` (`2025-07-01`)
