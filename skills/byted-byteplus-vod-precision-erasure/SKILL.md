---
name: byted-byteplus-vod-precision-erasure
description: "Upload video/audio media to BytePlus VOD (Video on Demand) storage, returning the Vid and playback references; supports local file upload (ApplyUploadInfo + TOS + CommitUploadInfo) and URL pull upload (UploadMediaByUrl); also submits precision erasure jobs on ingested media (StartExecution / Operation.Task.Erase): Auto OCR only — default subtitle-only erasure, optional full on-screen text, optional EraseOption ClipFilter (skip/selected); NewVid is always true; optional WithEraseInfo. Trigger keywords: precision erasure, precise erase, VOD upload, subtitle removal, OCR subtitles, remove on-screen text, erase text, StartExecution Erase."
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

# VOD precision erasure

Uploads video/audio to a BytePlus VOD space (from a **local file** or a **public URL**) and returns a `vid://…` reference. For media already in VOD, submits **precision erasure** tasks (`StartExecution` → `Operation.Task.Type: Erase`) using **automatic OCR only**. Do **not** tell end users they can change erasure **mode** between Manual and Auto — this skill always sends **`Auto`**. **`NewVid` is always `true`** (not surfaced as a user choice).

---

## Product scope

| Aspect | Behaviour |
|--------|-----------|
| **Input** | `Vid` or `DirectUrl` (JSON field `video`) |
| **Erasure coverage** | Default **subtitle only** (`Auto.Type: Subtitle`, `SubtitleFilter: {}`). User may opt into **all detected on-screen text** via `text: true` or `all_text: true` → `Auto.Type: Text`. |
| **Timeline** | Default: **whole** video (no `ClipFilter`). Optional `clip_filter` with **`mode`** `skip` or **`selected`** — when either is used, **`clips` is mandatory** (non-empty). |
| **Output asset** | **`NewVid` is always `true`** — not configurable and not prompted. |
| **Erasure metadata** | Default **`with_erase_info: true`** (`WithEraseInfo`). If `false`, stdout `EraseMeta` is `{}`; `VideoUrls` are still populated when `Erase.File` is returned. |

**Not supported:** `Manual` mode, custom ratio `Locations`, tuning `SubtitleFilter` beyond `{}`, `VideoOption.EncodeMode`, overriding `NewVid`.

**Precision erasure allowlist:** if you see HTTP **403** or “Permission denied”, explain allowlist / work order per [BytePlus VOD](https://console.byteplus.com/workorder/create?step=2&SubProductID=P00001112).

---

## Prerequisites

- **Environment variables** (required; optionally place a `.env` in the working directory — scripts load it automatically):
  - `BYTEPLUS_ACCESSKEY` — BytePlus Access Key
  - `BYTEPLUS_SECRETKEY` — BytePlus Secret Key
  - `VOD_SPACE_NAME` — VOD space name
- **Execution:** examples use `uv run python …` (`python scripts/…` works if deps are installed).

---

## Workflow overview

```text
Upload pipeline (local file):
  [S1_APPLY]  ApplyUploadInfo → TOS upload address + SessionKey
  [S2_TOS]    PUT file to TOS (direct or chunked)
  [S3_COMMIT] CommitUploadInfo → Vid
  Output: { Vid, Source, PlayURL, FileName, SpaceName, SourceUrl }

Upload pipeline (URL):
  [S1_UPLOAD] Submit URL upload job (UploadMediaByUrl) → JobId
  [S2_POLL]   Poll QueryUploadTaskInfo → Vid
  Output: { Vid, Source, PlayURL, FileName, SpaceName, SourceUrl, JobId }

Precision erasure pipeline:
  [S3_ERASE]  Submit Erase task (StartExecution / Task.Type Erase) → RunId
  [S4_POLL]   Poll GetExecution → output Erase.File (+ optional Erase.Info)
  Output: { Status, SpaceName, VideoUrls[{ FileId, Vid, DirectUrl, Source, Url }], EraseMeta? }
```

---

## Quick Self-Check (recommended)

Before running any script:

- `.env` or env vars contain `BYTEPLUS_ACCESSKEY`, `BYTEPLUS_SECRETKEY`, and `VOD_SPACE_NAME`.

Pick the pipeline from user intent:

| User intent | Pipeline | Entry script |
|-------------|----------|--------------|
| Upload video to VOD | Upload | `scripts/upload.py` |
| Subtitle / on-screen text erasure | Precision erasure | `scripts/precise_erase.py` |

---

## S1_UPLOAD & S2_POLL: Upload and Obtain Vid

### Calling convention

Run from the Skill root directory (`byted-byteplus-vod-precision-erasure/`):

```bash
# Local file upload (returns Vid when complete)
uv run python scripts/upload.py "/path/to/video.mp4" [space_name]

# URL upload (polls until Vid is returned)
uv run python scripts/upload.py "https://example.com/video.mp4" [space_name]

uv run python scripts/upload.py "https://example.com/sample.mp4" my_space
```

- First argument: **local file path** or public `http://` / `https://` URL (auto-detected).
- Second argument (optional): space name; if omitted, `VOD_SPACE_NAME` is used.
- Paths and URLs **must include a file extension** (e.g. `.mp4`, `.mov`, `.mp3`).

### Upload flow

**Local file** (synchronous, three-step):

1. `ApplyUploadInfo` (API version `2023-01-01`) → TOS address, SessionKey  
2. PUT to TOS (direct `< 20 MiB`, else chunked)  
3. `CommitUploadInfo` (`2023-01-01`) → `Vid`  

**URL pull** (async + poll):

1. `UploadMediaByUrl` (`2023-01-01`) → `JobId`  
2. Poll `QueryUploadTaskInfo` until done (same limits as sibling skill: typically 360 × 5 s)  
3. Return `Vid`  

### Output format

On success, one JSON object on stdout, e.g.:

```json
{
  "Vid": "v0d123abc",
  "Source": "vid://v0d123abc",
  "PlayURL": "https://example.cdn.com/xxx.m3u8",
  "PosterUri": "",
  "FileName": "uuid-filename.mp4",
  "SpaceName": "my_space",
  "SourceUrl": "https://example.com/video.mp4",
  "JobId": "job-xxx"
}
```

- Preserve **`Source`** (`vid://…`) for downstream skills.

### Timeout handling (URL upload)

If URL polling exhausts retries, stderr / JSON includes something like:

```json
{
  "error": "Polling timed out (360 attempts × 5s); the URL pull upload is still processing",
  "resume_hint": {
    "description": "The URL upload has not finished yet; retry with the command below",
    "command": "uv run python scripts/upload.py \"<original URL>\" [space_name]"
  },
  "JobIds": "job-xxx",
  "State": "running"
}
```

---

## S3_ERASE & S4_POLL: precision erasure

### Calling convention

Run from the Skill root directory (`byted-byteplus-vod-precision-erasure/`):

```bash
# Default: subtitle-only, whole video, WithEraseInfo on
uv run python scripts/precise_erase.py '{"type":"Vid","video":"v0310abc"}'

uv run python scripts/precise_erase.py '{"type":"Vid","video":"vid://v0d225gxxx"}' production_space

# Broader OCR (subtitle + other on-screen text)
uv run python scripts/precise_erase.py '{"type":"Vid","video":"v0310abc","text":true}'

uv run python scripts/precise_erase.py @params.json

# Resume after timeout
uv run python scripts/poll_execution.py '<RunId>' [space_name]
```

### Parameter reference

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `type` | string | ✅ | `Vid` or `DirectUrl` |
| `video` | string | ✅ | Vid or VOD `FileName`; `vid://` / `directurl://` stripped automatically |
| `text` | boolean | no | If true: **`Auto.Type: Text`** (more aggressive). Default false → subtitle-only. |
| `all_text` | boolean | no | Synonym for **`text`** (if both are set, **`text`** is applied first). |
| `clip_filter` | object | no | Omit = whole video. If set: **`mode`** `skip` or `selected`, and **`clips`** (non-empty list of `{ "start", "end" }` seconds; `Start`/`End` accepted). |
| `with_erase_info` | boolean | no | Default `true` (`WithEraseInfo`). If `false`, detailed erase geometry is not requested; stdout **`EraseMeta`** is `{}`. |

Do **not** prompt users for **Manual mode** or **NewVid**.

### Agent prompting (plain language)

Clarify: **subtitle-only** vs **all on-screen text**; **whole video** vs **segments** (`skip` / `selected` + `clips`); whether they need **region-level erase telemetry** (`with_erase_info`). Use conversational labels — avoid exposing raw JSON field names unless the user asks for implementation details.

### Output format

On success, one JSON object on stdout, roughly:

```json
{
  "Status": "Success",
  "SpaceName": "my_space",
  "VideoUrls": [
    {
      "FileId": "…",
      "Vid": "v0…",
      "DirectUrl": "path/to/output.mp4",
      "Source": "vid://v0…",
      "Url": "https://example.cdn.com/…"
    }
  ],
  "AudioUrls": [],
  "Texts": [],
  "EraseMeta": {
    "Duration": 57.099,
    "Info": {}
  }
}
```

When **`with_erase_info`** was false, **`EraseMeta`** is `{}`.

- **`VideoUrls[0].Url`:** playable / downloadable when signing succeeds for the space.  
- **`Source`:** prefer `vid://…` when the API returns a new `Vid`; else `directurl://…`.

### Timeout handling (GetExecution polling)

Same pattern as the enhancement skill:

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

## Environment Variables

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

---

## Error Output Format

All failures use:

```json
{"error": "error description"}
```

---

## References

- [BytePlus VOD Python SDK](https://docs.byteplus.com/en/docs/byteplus-vod/docs-python-sdk)
- [precision erasure parameter reference](references/precise_erase.md)
- API: `ApplyUploadInfo` (`2023-01-01`)
- API: `CommitUploadInfo` (`2023-01-01`)
- API: `UploadMediaByUrl` (`2023-01-01`)
- API: `QueryUploadTaskInfo` (`2023-01-01`)
- API: `StartExecution` (`2025-07-01`)
- API: `GetExecution` (`2025-07-01`)
