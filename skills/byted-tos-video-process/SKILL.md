---
name: byted-tos-video-process
description: "Inspects videos, extracts frames, and concatenates video clips stored in Volcengine TOS: read video metadata, capture single snapshots, batch-capture multiple frames by explicit timestamps or interval, concatenate multiple video clips, and save results locally or back to TOS. Use this skill when the user needs to get video duration or codec info, capture a poster image or thumbnail, extract frames at specific timestamps, sample frames at regular intervals, merge or join multiple video clips into one — even if they don't explicitly mention 'video processing' or 'frame extraction'."
metadata:
  version: "1.0.0"
  openclaw:
    identity:
      - type: apikey
        provider: tos_provider
        env:
          - TOS_ACCESS_KEY
          - TOS_SECRET_KEY
          - TOS_ENDPOINT
          - TOS_REGION
          - TOS_BUCKET
        required: true
    optional:
      env:
        - TOS_OBJECT_KEY
        - TOS_SECURITY_TOKEN
        - TOS_SAVEAS_BUCKET
        - TOS_SAVEAS_OBJECT_PREFIX
user-invocable: true
license: Apache-2.0
---

# Volcengine TOS Video Process

Inspect videos, extract frames, and concatenate video clips stored in Volcengine TOS — metadata lookup, single snapshot, multi-frame capture, video concatenation, and TOS-to-TOS persistence.

## Setup (once per environment)

Install dependencies on first use:

```bash
cd {baseDir}
pip install -r {baseDir}/requirements.txt
```

Then run scripts with Python 3.7+:

```bash
python3 {baseDir}/scripts/<script>.py <args>
```

If you see a `ModuleNotFoundError` for `tos`, reinstall dependencies.

## Environment Variables

This skill relies on the TOS identity declared in the `metadata` block. Common runtime variables are:

| Environment Variable | Required | Description |
| --- | --- | --- |
| `TOS_ACCESS_KEY` | Yes | TOS access key ID |
| `TOS_SECRET_KEY` | Yes | TOS secret access key |
| `TOS_ENDPOINT` | Yes | TOS endpoint URL |
| `TOS_REGION` | Yes | TOS region |
| `TOS_BUCKET` | Yes | Source bucket that stores the video |
| `TOS_OBJECT_KEY` | No | Source object key of the video. Some scripts accept alternatives, while `video_info.py` and `video_snapshot.py` read this value from the environment |
| `TOS_SECURITY_TOKEN` | No | STS session token when using temporary credentials |
| `TOS_SAVEAS_BUCKET` | No | Default target bucket for saving snapshots |
| `TOS_SAVEAS_OBJECT_PREFIX` | No | Default key prefix for saving snapshots |

## Quick start (common tasks)

```bash
# Read video metadata (resolution, duration, codec)
TOS_OBJECT_KEY=demo.mp4 python3 {baseDir}/scripts/video_info.py

# Capture a single frame at 5 seconds
TOS_OBJECT_KEY=demo.mp4 python3 {baseDir}/scripts/video_snapshot.py --time 5000 --output frame_5s.jpg

# Capture multiple frames and save locally
python3 {baseDir}/scripts/video_snapshots.py --key demo.mp4 --timestamps 1000 3000 5000

# Capture multiple frames by interval
python3 {baseDir}/scripts/video_snapshots.py --key demo.mp4 \
  --interval-ms 5000 --duration-ms 60000 --output-dir snapshots

# Capture multiple frames and save to TOS
python3 {baseDir}/scripts/video_snapshots.py --key demo.mp4 --timestamps 1000 3000 5000 --save-to-tos

# Concatenate multiple video clips
python3 {baseDir}/scripts/video_concat.py --key clip1.mp4 --fragments "clip2.mp4,clip3.mp4" --output-key merged.mp4 --wait
```

## Available scripts

| Script | Purpose |
|--------|---------|
| `scripts/video_info.py` | Read video metadata (format, duration, resolution, codec, frame rate). |
| `scripts/video_snapshot.py` | Capture a single frame at a given timestamp. Supports local save or TOS-to-TOS persistence. |
| `scripts/video_snapshots.py` | Batch-capture multiple frames across a timeline. Supports explicit timestamps, interval mode, concurrent execution, and TOS-to-TOS persistence. |
| `scripts/video_concat.py` | Concatenate multiple video clips into one. Uses TOS gateway `media_jobs` async API with `job_type=Concat`. Supports `--wait` to poll until completion. |

`video_snapshots.py` and `video_concat.py` support `--key`-style object selection. `video_info.py` and `video_snapshot.py` currently read `TOS_OBJECT_KEY` from the environment. `video_snapshots.py` also supports `--bucket` override for multi-bucket testing. Run any script with `-h` for full usage.

## Out of scope

- Full video transcoding pipelines (this skill covers metadata + frame extraction + concatenation only).
- Image-only or document-only workflows (use `byted-tos-image-process` or `byted-tos-doc-process`).
- Non-TOS storage providers.

## Rules

- **Authentication**: Authentication is provided by the TOS identity declared in the `metadata` block above. Object selection can be overridden per script with `--key`.
- **Timestamp unit**: All timestamp parameters are in **milliseconds** (e.g., `5000` = 5 seconds).
- **Validate timestamps**: Ensure snapshot timestamps do not exceed the video duration. Use `video_info.py` to read duration first when needed.
- **Save to TOS**: Use `--save-to-tos` with `TOS_SAVEAS_BUCKET` / `TOS_SAVEAS_OBJECT_PREFIX` to persist snapshots back to TOS without local download.
- **Parameter source of truth**: Official Volcengine TOS documentation is authoritative for the full `video/snapshot` parameter matrix. When uncertain, check [REFERENCE.md](REFERENCE.md).
- **Language**: Reply in the user's preferred language.

## Further reading

- Setup and environment: [README.md](README.md)
- Parameter reference: [REFERENCE.md](REFERENCE.md)
- End-to-end workflows: [WORKFLOWS.md](WORKFLOWS.md)
