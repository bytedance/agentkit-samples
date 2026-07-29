---
name: byted-tos-image-process
description: "Transforms and inspects image objects stored in Volcengine TOS. Use this skill only when the task explicitly involves a TOS bucket/object key, TOS image processing, TOS-to-TOS save-as output, or Volcengine TOS image process syntax such as image/info, image/resize, image/format, image/watermark, image/draw, image/blindwatermark, or image/understanding. Do not use this skill for ordinary uploaded screenshots, local images, UI screenshot analysis, generic OCR, face detection, or visual question answering unless the user clearly says the image is a TOS object or asks to process/save it through TOS."
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
license: Apache-2.0
---

# Volcengine TOS Image Process

Inspect and transform images stored in Volcengine TOS — metadata, format conversion, resize, watermark, blind watermark, and AI-powered image understanding.

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
| `TOS_BUCKET` | Yes | Source bucket that stores the image |
| `TOS_OBJECT_KEY` | No | Source object key of the image. Can be overridden with `--key` |
| `TOS_SECURITY_TOKEN` | No | STS session token when using temporary credentials |
| `TOS_SAVEAS_BUCKET` | No | Default target bucket for saving processed results |
| `TOS_SAVEAS_OBJECT_PREFIX` | No | Default key prefix for saving processed results |

## Quick start (common tasks)

```bash
# Read image metadata
python3 {baseDir}/scripts/image_info.py --key photo.jpg

# Convert to WebP
python3 {baseDir}/scripts/image_format.py --key photo.jpg --f webp --output converted.webp

# Resize to width 500
python3 {baseDir}/scripts/image_resize.py --key photo.jpg --width 500 --output resized.jpg

# Draw points and connecting lines
python3 {baseDir}/scripts/image_draw.py --key photo.jpg \
  --points 50x50-200x120-320x220 --line --color FF0000 --output draw.jpg

# Zoom by resize + crop
python3 {baseDir}/scripts/image_zoom.py --key photo.jpg \
  --resize-w 1200 --crop-w 500 --crop-h 400 --gravity center --output zoom.jpg

# Add visible text watermark
python3 {baseDir}/scripts/image_watermark.py --key photo.jpg \
  --text "My Brand" --font fangzhengshusong --color FF0000 --size 72 \
  --gravity center --output watermarked.jpg

# Embed blind watermark (requires ≥512×512 image and account permission)
python3 {baseDir}/scripts/image_blindwatermark.py --key photo.jpg \
  --kv text=HelloBlind --output blind.jpg

# Run a custom process string
python3 {baseDir}/scripts/image_process.py --key photo.jpg \
  --process "image/resize,w_300,h_300,m_fill" --output filled.jpg

# Preview the resolved request without calling TOS
python3 {baseDir}/scripts/image_resize.py --key photo.jpg \
  --width 500 --dry-run --json

# AI-powered understanding for a TOS image object (requires whitelist)
python3 {baseDir}/scripts/image_understanding.py --key photo.jpg \
  --prompt "Describe this image in detail"
python3 {baseDir}/scripts/image_understanding.py --key document.png \
  --prompt "识别图片中的所有文字内容"
```

## Available scripts

| Script | Purpose |
|--------|---------|
| `scripts/image_info.py` | Read image metadata (format, dimensions, size). Falls back to local parsing when TOS returns raw bytes. |
| `scripts/image_format.py` | Convert format (jpg, png, webp) with optional quality setting. |
| `scripts/image_resize.py` | Resize by width/height/mode. |
| `scripts/image_draw.py` | Draw points and optional connecting lines on an image with `image/draw`. |
| `scripts/image_zoom.py` | Build agent-friendly zoom results by chaining `image/resize` and `crop`. |
| `scripts/image_watermark.py` | Add visible text or image watermark with positioning, rotation, tiling, and opacity. |
| `scripts/image_blindwatermark.py` | Embed blind watermark. Requires account-level permission and image ≥512×512 px. |
| `scripts/image_process.py` | Pass any raw `image/...` process string. |
| `scripts/image_understanding.py` | AI-powered understanding for TOS image objects via VLM (doubao-seed-1.6-vision). Supports description, OCR, face detection, and visual Q&A only when the source image is a TOS object. Requires account whitelist. |

All scripts support `--key` to override `TOS_OBJECT_KEY`, `--output` for local save, and `--saveas-bucket`/`--saveas-object` for TOS-to-TOS persistence. `TOS_SAVEAS_BUCKET` and `TOS_SAVEAS_OBJECT_PREFIX` are used as defaults when save-as CLI arguments are omitted. Most scripts support `--json` for machine-readable output, and all process-building scripts support `--dry-run` to preview the resolved request without calling TOS. Run any script with `-h` for full usage.

## Out of scope

- Editing images with local desktop tooling outside TOS.
- Ordinary uploaded screenshots, local image files, mobile UI screenshots, generic OCR, face detection, and visual question answering that do not involve a TOS bucket/object key. Use the model's native vision or local file tools instead.
- Video or document processing (use `byted-tos-video-process` or `byted-tos-doc-process`).
- Non-TOS storage providers.

## Rules

- **Authentication**: Authentication is provided by the TOS identity declared in the `metadata` block above. Object selection can be overridden per script with `--key`.
- **Credential safety**: Never print credential environment variable values such as `TOS_ACCESS_KEY`, `TOS_SECRET_KEY`, `TOS_SECURITY_TOKEN`, or model API keys. Validate behavior by running the scripts directly instead of echoing or dumping the environment.
- **Trigger boundary**: Use this skill only for Volcengine TOS image objects or TOS image process workflows. If the user attaches or references a normal local image/screenshot and does not mention TOS, do not invoke these scripts; answer with native vision/local-file capabilities instead.
- **Dry run**: Use `--dry-run --json` to validate parameters and inspect the generated `process` string. Dry-run does not call TOS and does not require AK/SK. If bucket/key are not provided, dry-run uses explicit placeholders where possible; real execution still requires valid TOS credentials, bucket/key, and network access.
- **Parameter source of truth**: The exact `process` string syntax is defined by official Volcengine TOS documentation. When uncertain, check [REFERENCE.md](REFERENCE.md).
- **Watermark encoding**: Text and font parameters in `image/watermark` require URL-safe Base64 encoding. The watermark script handles this automatically when you pass `--text` and `--font`.
- **Blind watermark constraints**: The source image must be at least 512×512 pixels, and the account must have the blind watermark capability enabled. If the capability is missing, the script exits with `[SKIP]` (use `--strict` to fail hard).
- **Image understanding**: Uses `image/understanding` with the `doubao-seed-1.6-vision` VLM model for TOS image objects only. The `--prompt` parameter is required. Requires account whitelist. Response time is typically 10-60 seconds.
- **Language**: Reply in the user's preferred language.

## Further reading

- Setup and environment: [README.md](README.md)
- Parameter reference: [REFERENCE.md](REFERENCE.md)
- End-to-end workflows: [WORKFLOWS.md](WORKFLOWS.md)
