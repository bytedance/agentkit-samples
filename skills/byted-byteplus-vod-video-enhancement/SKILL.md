---
name: byted-byteplus-vod-video-enhancement
description: "Upload video/audio media to BytePlus VOD (Video on Demand) storage, returning the Vid and playback references; supports both local file upload (ApplyUploadInfo + TOS + CommitUploadInfo) and URL pull upload (UploadMediaByUrl); also supports AI-based comprehensive quality restoration on already-uploaded videos (removing compression artifacts, noise, scratches, improving clarity, and configuring Pro-tier color depth). Trigger keywords: upload video, upload media, upload to VOD, URL upload, pull upload, local upload, file upload, UploadMediaByUrl, ApplyUploadInfo, media ingestion, quality restoration, quality enhancement, comprehensive restoration, video denoising, denoise, compression artifact removal, color depth, bit depth, 10-bit, 12-bit, 16-bit."
version: 1.2.0
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

# VOD_video enhancement

Uploads video/audio to a BytePlus VOD space (from a **local file** or a **public URL**) and returns a `vid://vxxxx` reference. Additionally provides AI-based comprehensive quality restoration that removes compression artifacts, noise, and scratches from ingested videos, improving overall clarity and color rendition.

---

## Prerequisites

- **Environment variables** (required, can be configured via a `.env` file in the working directory — the scripts will load it automatically):
  - `BYTEPLUS_ACCESSKEY` — BytePlus Access Key
  - `BYTEPLUS_SECRETKEY` — BytePlus Secret Key
  - `VOD_SPACE_NAME` — VOD space name
- **Execution**: examples use `uv run python ...` (if the host environment can run Python directly, `python scripts/...` also works).

---

## Workflow Overview

```text
Upload pipeline (local file):
  [S1_APPLY]  ApplyUploadInfo → returns TOS upload address + SessionKey
  [S2_TOS]    PUT file to TOS (direct or chunked)
  [S3_COMMIT] CommitUploadInfo → returns Vid
  Output: { Vid, Source, PlayURL, FileName, SpaceName, SourceUrl }

Upload pipeline (URL):
  [S1_UPLOAD] Submit URL upload job (UploadMediaByUrl) → returns JobId
  [S2_POLL]   Poll QueryUploadTaskInfo → returns Vid
  Output: { Vid, Source, PlayURL, FileName, SpaceName, SourceUrl, JobId }

Quality restoration pipeline:
  [S3_ENHANCE] Submit restoration job (StartExecution/enhanceVideo) → returns RunId
  [S4_POLL]    Poll GetExecution → returns the restored file
  Output: { Status, SpaceName, VideoUrls[{ FileId, DirectUrl, Source }] }
```

---

## Quick Self-Check (recommended)

Before running any script, confirm the following (avoid unrelated Python/uv version checks):

- `.env` or environment variables contain:
  - `BYTEPLUS_ACCESSKEY` + `BYTEPLUS_SECRETKEY`
  - `VOD_SPACE_NAME`

Once verified, pick the corresponding pipeline based on user intent:

| User intent | Pipeline | Entry script |
|-------------|----------|--------------|
| Upload video to VOD | Upload pipeline | `scripts/upload.py` |
| Quality restoration / denoise / remove compression artifacts | Quality restoration pipeline | `scripts/quality_enhance.py` |

---

## S1_UPLOAD & S2_POLL: Upload and Obtain Vid

### Calling Convention

Run from the Skill root directory (`byted-byteplus-vod-video-enhancement/`):

```bash
# Local file upload (synchronous — returns Vid when complete)
uv run python scripts/upload.py "/path/to/video.mp4" [space_name]

# URL upload (automatically polls until a Vid is returned)
uv run python scripts/upload.py "<https://example.com/video.mp4>" [space_name]

# Example: specifying the space
uv run python scripts/upload.py "https://example.com/sample.mp4" my_space
```

- First argument: either a **local file path** or a public `http://` / `https://` link. The script auto-detects which mode to use.
- Second argument (optional): the VOD space name; when omitted it is read from the environment variable `VOD_SPACE_NAME`.
- The file / URL must carry a file extension (such as `.mp4`, `.mov`, `.mp3`), otherwise an error is raised.

### Upload Flow

**Local file upload** (synchronous, three-step):
1. Call `ApplyUploadInfo` (API Version: 2023-01-01) to obtain the TOS upload address, authentication token, and SessionKey.
2. PUT the file to TOS (direct upload for files < 20 MiB, chunked upload otherwise).
3. Call `CommitUploadInfo` (API Version: 2023-01-01) with the SessionKey; returns the `Vid`.

**URL upload** (two-phase asynchronous):
1. Call `UploadMediaByUrl` (API Version: 2023-01-01) to submit the pull job; returns a `JobId`.
2. Poll `QueryUploadTaskInfo` until the job completes, with a maximum wait of 30 minutes (360 × 5s).
3. Once the job is complete, return the `Vid`.

### Output Format

On success, a JSON line is printed to stdout:

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

- `Source`: a `vid://`-formatted reference that can be passed directly to follow-up skills such as `byted-mediakit`.
- The host agent should save the `Source` field for use in subsequent processing steps.

### Timeout Handling

If polling times out (30 minutes), the output is:

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

## S3_ENHANCE & S4_POLL: AI Comprehensive Quality Restoration

### Calling Convention

Run from the Skill root directory (`byted-byteplus-vod-video-enhancement/`):

```bash
# Submit after the user has explicitly selected both config and repair_style
uv run python scripts/quality_enhance.py '{"type":"Vid","video":"v0310abc","config":"common","repair_style":1}'

# Example: a vid:// prefix is also accepted (the script strips it automatically)
uv run python scripts/quality_enhance.py '{"type":"Vid","video":"vid://v0d225gxxx","config":"common","repair_style":1}' production_space

# Optional target output resolution (omit res for source resolution)
uv run python scripts/quality_enhance.py '{"type":"Vid","video":"v0310abc","config":"common","repair_style":1,"res":"1080p"}'

# Optional color depth (Pro only; online output supports 8, 10, 12, or 16 bit)
uv run python scripts/quality_enhance.py '{"type":"Vid","video":"v0310abc","config":"common","repair_style":2,"bit_depth":10}'

# 16-bit FFV1 output (input video must be 40 seconds or shorter)
uv run python scripts/quality_enhance.py '{"type":"Vid","video":"v0310abc","config":"common","repair_style":2,"bit_depth":16}'

# Pass parameters via @file.json (recommended — avoids shell escaping issues)
uv run python scripts/quality_enhance.py @params.json

# Resume polling after a timeout
uv run python scripts/poll_execution.py '<RunId>' [space_name]
```

### Parameter Reference

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `type` | string | ✅ | `Vid` (video ID) or `DirectUrl` (VOD storage FileName) |
| `video` | string | ✅ | The video Vid or FileName (a `vid://` prefix is accepted and automatically stripped) |
| `config` | string | ✅ | VolcMoeEnhanceParam `Config`; one of `common`, `ugc`, `short_series`, `aigc`, `old_film`. If the user explicitly asks for defaults, use `common`. |
| `repair_style` | integer | ✅ | VolcMoeEnhanceParam `VideoStrategy.RepairStyle`; `1` = Standard, `2` = Pro. If the user explicitly asks for defaults, use `1`. |
| `res` | string | no | Optional `MoeEnhance.Target.Res` — target output resolution. Omit or leave empty for **source resolution** (no upscaling target). Allowed: `240p`, `360p`, `480p`, `540p`, `720p`, `1080p`, `2k`, `4k`. |
| `bit_depth` | integer | no | Optional `MoeEnhance.Target.BitDepth`; Pro tier only. Online output supports `8`, `10`, `12`, or `16`. Omit it to use the API default, `8`. `8` uses H.264; `10` and `12` use H.265; `16` uses lossless FFV1. |

Before quality restoration, you MUST ask the user to choose both required enhancement parameters if either `config` or `repair_style` is missing. Do not silently use defaults. Only use `config=common` and `repair_style=1` when the user explicitly asks for default/recommended settings. When asking the user, use plain product language only; do not show internal parameter names or values such as `config=...`, `repair_style=...`, `common`, or `short_series` in the question text or option labels.

Suggested prompt:

> Video enhancement may take some time. Choosing the right template usually gives better results.  
> What type of video is it?  
> 1. General video  
> 2. Short video / UGC  
> 3. Short drama / short series  
> 4. AI-generated content  
> 5. Old film / classic footage that needs restoration  
>   
> Which video enhancement tier would you like to use?  
> 1. Standard: balanced visual improvement and processing speed  
> 2. Pro: cinematic-grade restoration with longer processing time; allowlist access may be required  
>   
> What output resolution do you want? (optional)  
> - Keep the **same as the source video** (recommended default — do not pass `res`)  
> - Or choose a target: 240p, 360p, 480p, 540p, 720p, 1080p, 2K, 4K
>
> If you chose Pro, what color depth do you want? (optional)
> - 8-bit (API default, H.264, broad compatibility)
> - 10-bit (recommended for premium delivery and HDR workflows, H.265)
> - 12-bit (professional post-production, H.265; requires compatible professional tools and displays)
> - 16-bit (lossless FFV1; source video must be 40 seconds or shorter; processed serially and may take longer)

If the user wants **source / original resolution**, **omit `res`** from the JSON (or use an empty string). Only set `res` when they explicitly pick a target resolution.

If the user asks for a default recommendation, use `config=common` and `repair_style=1` with **no `res` or `bit_depth`**. Otherwise, wait for the user's selections before running `scripts/quality_enhance.py`.

Internal mapping: General video -> `config=common`; Short video / UGC -> `config=ugc`; Short drama / short series -> `config=short_series`; AI-generated content -> `config=aigc`; Old film / classic footage -> `config=old_film`; Standard -> `repair_style=1`; Pro -> `repair_style=2`; source resolution -> omit `res`; 240p–4K -> `res` as listed in the parameter table (`2k` / `4k` in JSON); selected color depth -> `bit_depth=8`, `10`, `12`, or `16`. Do not expose these parameter names or values in the question unless the user asks for implementation details.

Color-depth usage limits:

- `bit_depth` can be submitted only with Pro (`repair_style=2`) and is part of the advanced enhancement output settings.
- The online API supports 8-bit, 10-bit, 12-bit, and 16-bit output.
- Before submitting 16-bit, confirm that the input video is **40 seconds or shorter**. The script cannot infer source duration from the current arguments, so do not submit until this requirement is confirmed.
- 16-bit uses FFV1 lossless encoding, so do not configure a target bitrate. This skill does not expose or send a target bitrate.
- 16-bit tasks are processed serially, one at a time. Set the expectation that processing may take longer and wait for the current task to finish before submitting another 16-bit task.
- 10-bit and 12-bit output uses H.265. For 12-bit review, ordinary players and SDR operating-system pipelines may render incorrectly; recommend a color-managed professional tool and monitor. The documentation recommends MOV with H.265 `yuv444p12le` for 12-bit delivery because conventional MP4/H.264/H.265 workflows are generally limited to 8-bit or 10-bit and may dither or truncate higher precision.
- Ordinary players and SDR rendering pipelines may also render 16-bit incorrectly. Review 16-bit output in a color-managed professional tool on a compatible monitor, and use high-throughput storage such as a dedicated NVMe SSD for large lossless assets.

Special handling for Pro: if the user chooses `repair_style=2` and the StartExecution/GetExecution response returns HTTP status `403`, or any error message contains `Permission denied`, explain that Pro is only available to users on the allowlist. Ask the user to submit a ticket to apply: https://console.byteplus.com/workorder/create

### Output Format

On success, a JSON line is printed to stdout:

```json
{
  "Status": "Success",
  "SpaceName": "my_space",
  "VideoUrls": [
    {
      "FileId": "xxx",
      "DirectUrl": "path/to/output.mp4",
      "Source": "directurl://path/to/output.mp4",
      "Url": "https://example.cdn.com/path/to/output.mp4?auth_key=..."
    }
  ],
  "AudioUrls": [],
  "Texts": []
}
```

- `VideoUrls[0].Url`: a directly accessible/downloadable URL (the script signs it based on the space's domain/auth rules).
- `VideoUrls[0].Source` (`directurl://...`) can be passed directly to downstream skills.

### Timeout Handling

If polling times out (30 minutes), the output is:

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
| `VOD_URL_EXPIRE_MINUTES` | Signed URL expiration (minutes, default 60) | No |
| `VOD_PLAY_DOMAIN` | Force the use of a specific play domain (optional, highest priority) | No |

---

## Error Output Format

All errors share the same format:

```json
{"error": "error description"}
```

---

## References

- [BytePlus VOD Python SDK](https://docs.byteplus.com/en/docs/byteplus-vod/docs-python-sdk)
- [Quality restoration parameter reference](references/quality-enhance.md)
- API: `ApplyUploadInfo` (Version: 2023-01-01)
- API: `CommitUploadInfo` (Version: 2023-01-01)
- API: `UploadMediaByUrl` (Version: 2023-01-01)
- API: `QueryUploadTaskInfo` (Version: 2023-01-01)
- API: `StartExecution` (Version: 2025-07-01)
- API: `GetExecution` (Version: 2025-07-01)
