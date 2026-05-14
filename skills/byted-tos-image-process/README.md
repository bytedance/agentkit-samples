# Bytedance TOS Image Process Skill

This skill provides a clean, reusable image-processing toolkit for files stored in Bytedance TOS. It focuses on the Volcengine TOS image processing syntax and demonstrates practical ways to inspect, convert, resize, draw annotations, build zoom-style crops, watermark, and persist processed results.

## When To Use

Use this skill when you need to:
- Read image metadata with `image/info`
- Convert formats such as `jpg`, `png`, and `webp`
- Generate thumbnails or resize images
- Draw points or connecting lines on an image
- Produce zoom-like results with resize plus crop
- Apply visible text or image watermarks
- Embed or extract blind watermarks
- Run a custom `image/...` process rule and save the result locally or back to TOS

Do not use this skill for:
- Video snapshot workflows
- Document preview or office conversion
- Generic storage operations that do not involve TOS image processing

## How It Works

Image processing is performed by passing a formatted `process` string to the Volcengine TOS SDK. Common examples include:

- `image/info`
- `image/format,webp,q_80`
- `image/resize,w_500,m_lfit`
- `image/watermark,...`
- `image/blindwatermark,...`

The scripts in this skill package show how to construct these rules, execute them through the SDK, and handle local or TOS-based outputs.

## Directory Layout

```text
byted-tos-image-process/
├── SKILL.md
├── README.md
├── REFERENCE.md
├── WORKFLOWS.md
├── LICENSE
├── requirements.txt
└── scripts/
    ├── image_info.py
    ├── image_format.py
    ├── image_resize.py
    ├── image_draw.py
    ├── image_zoom.py
    ├── image_watermark.py
    ├── image_blindwatermark.py
    ├── image_understanding.py
    └── image_process.py
```

## Requirements

- Python 3.7+
- Access to Volcengine TOS
- Valid AK/SK or STS credentials
- Network access to the target TOS endpoint

Install dependencies:

```bash
pip install -r requirements.txt
```

## Environment Variables

| Variable | Required | Description | Example |
| --- | --- | --- | --- |
| `TOS_ACCESS_KEY` | Yes | TOS access key ID. | `AK...` |
| `TOS_SECRET_KEY` | Yes | TOS secret access key. | `your-secret-key` |
| `TOS_ENDPOINT` | Yes | TOS endpoint URL. | `https://tos-cn-beijing.volces.com` |
| `TOS_REGION` | Yes | TOS region. | `cn-beijing` |
| `TOS_BUCKET` | Yes | Source bucket that stores the image. | `my-image-bucket` |
| `TOS_OBJECT_KEY` | Yes | Source object key of the image. | `input/photos/landscape.jpg` |
| `TOS_SECURITY_TOKEN` | No | STS session token when using temporary credentials. | `STS...` |
| `TOS_SAVEAS_BUCKET` | No | Default target bucket for saving processed results. | `my-output-bucket` |
| `TOS_SAVEAS_OBJECT_PREFIX` | No | Default key prefix for saving processed results. | `processed/images/` |

For production usage, prefer short-lived STS credentials. The SDK automatically uses `TOS_SECURITY_TOKEN` when it is present.

## Quick Start

Export the minimum required configuration:

```bash
export TOS_ACCESS_KEY="YOUR_AK"
export TOS_SECRET_KEY="YOUR_SK"
export TOS_ENDPOINT="https://tos-cn-beijing.volces.com"
export TOS_REGION="cn-beijing"
export TOS_BUCKET="your-image-bucket"
export TOS_OBJECT_KEY="path/to/your/image.jpg"
```

Run one of the ready-to-use examples:

Read image metadata:

```bash
python3 scripts/image_info.py
```

If the service returns raw image bytes instead of a JSON metadata payload, the script falls back to local parsing and prints basic information such as format, file size, width, and height.

Convert to WebP:

```bash
python3 scripts/image_format.py --f webp --q 80 --output converted.webp
```

Resize to width 500:

```bash
python3 scripts/image_resize.py --w 500 --output resized.jpg
```

Draw points and lines:

```bash
python3 scripts/image_draw.py \
  --points 50x50-200x120-320x220 \
  --line \
  --color FF0000 \
  --output draw.jpg
```

Create a zoom-style crop:

```bash
python3 scripts/image_zoom.py \
  --resize-w 1200 \
  --crop-w 500 \
  --crop-h 400 \
  --gravity center \
  --output zoom.jpg
```

Apply a visible watermark and save back to TOS:

```bash
python3 scripts/image_watermark.py \
  --text "My Brand" \
  --font fangzhengshusong \
  --color FF0000 \
  --size 72 \
  --gravity se \
  --x 20 \
  --y 20 \
  --saveas-bucket "your-output-bucket" \
  --saveas-object "watermarked/image.jpg"
```

If you already have official URL-safe Base64 values, use `--text-b64`, `--font-b64`, or `--image-b64` directly. For image watermarks, pass the raw watermark object reference with `--image`, and the script will URL-safe-Base64 encode it for the `image` parameter.

Apply a blind watermark:

```bash
python3 scripts/image_blindwatermark.py \
  --kv text=HelloBlind \
  --output blindwatermarked.jpg
```

**Blind watermark prerequisites:**
- The account/bucket must have blind watermark capability enabled in the TOS console.
- The source image must be at least **512×512 pixels**.

If the capability is not enabled, the script prints `[SKIP]` and exits successfully by default. Use `--strict` to treat that as a hard failure. If the image is too small, a clear error message is printed.

Run a custom processing rule:

```bash
python3 scripts/image_process.py \
  --process "image/resize,w_300,h_300,m_fill" \
  --output filled_300x300.jpg
```

## Document Roles

- `SKILL.md`: trigger-oriented instructions for agents deciding whether to load this skill
- `README.md`: setup guide and runnable entry points for humans and agents
- `REFERENCE.md`: parameter reference and result semantics
- `WORKFLOWS.md`: common image-processing patterns
- `scripts/`: executable examples for common image-processing tasks

## Usage Notes

- The exact `process` string syntax is defined by TOS and should be treated as authoritative.
- Dedicated scripts expose common arguments directly, while advanced parameters can usually be passed with `--kv key=value`.
- The image scripts now consistently support `--bucket` / `--key`, `--output` for local save, `--saveas-bucket` / `--saveas-object` for TOS persistence, and `--json` for machine-readable output. Several scripts also support `--dry-run` to show the resolved request before calling TOS.
- `image_draw.py` is useful for agent outputs such as marking detections, key points, or polygon-like paths using `image/draw`.
- `image_zoom.py` wraps the common "resize first, then crop the interesting region" pattern that agents often need for visual focus.
- The watermark helper now follows the official parameter model: `text/type/color/size/shadow/rotate/fill` for text, `image` for image watermark, `g/x/y/voffset/t` for base placement, and `order/align/interval` for mixed watermark.
- Saving results back to TOS is often more efficient than downloading locally for downstream workflows.
- Some environments may return raw image bytes for `image/info`; the script prints fallback metadata in that case instead of failing.

## Related Files

- Parameter reference: [REFERENCE.md](REFERENCE.md)
- Workflow guide: [WORKFLOWS.md](WORKFLOWS.md)

## License

This skill is licensed under the Apache License 2.0. See [LICENSE](LICENSE).
