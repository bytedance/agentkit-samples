# Bytedance TOS Image Process SDK Reference

This document provides a reference for the parameters and return values of the core image processing operations, as implemented via the Volcengine TOS Python SDK.

**Crucial Note**: The image processing capabilities of TOS are extensive. This document covers the high-level structure and common parameters. For an exhaustive list of all parameters, options, and their exact syntax (e.g., for watermarks, custom cuts), **you must refer to the official Volcengine TOS image processing documentation.**

## Table of Contents
- [Authentication](#authentication)
- [Core Operations](#core-operations)
  - [1. `ImageInfo`](#1-imageinfo)
  - [2. `ImageFormat`](#2-imageformat)
  - [3. `ImageResize`](#3-imageresize)
  - [4. `ImageDraw`](#4-imagedraw)
  - [5. `ImageZoom`](#5-imagezoom)
  - [6. `ImageWatermark`](#6-imagewatermark)
  - [7. `ImageBlindWatermark`](#7-imageblindwatermark)
  - [8. `ImageProcess` (Generic)](#8-imageprocess-generic)
  - [9. `ImageUnderstanding`](#9-imageunderstanding)
- [Data Models](#data-models)
  - [ImageInfo Object](#imageinfo-object)
  - [ProcessSaveResult Object](#processsaveresult-object)

---

## Authentication

Authentication is handled automatically by the `tos.TosClientV2` client during initialization. Credentials should be provided via environment variables as described in the `README.md`.

---

## Core Operations

Image processing is invoked by passing a specially formatted `process` string to the `get_object`, `get_object_to_file`, or other relevant methods of the TOS SDK client.

### 1. `ImageInfo`

Retrieves metadata for a specified image object in TOS.

**Process String:** `image/info`

**SDK Method:** `client.get_object()`

**Key Parameters:**

| Parameter | Type   | Required | Description                                    |
|-----------|--------|----------|------------------------------------------------|
| `bucket`  | string | Yes      | The name of the bucket containing the image.   |
| `key`     | string | Yes      | The full object key (path) of the image file.  |
| `process` | string | Yes      | Must be the exact string `"image/info"`.       |

**Success Response:**
- In the ideal case, the SDK response body contains a `bytes` object with a JSON string.
- In some environments, `image/info` may return raw image bytes instead of a JSON payload. The companion script `scripts/image_info.py` detects that case and falls back to local parsing for basic fields such as format, width, height, and file size.

### 2. `ImageFormat`

Converts the image to a different format and/or adjusts its quality.

**Process String:** `image/format,<format>,q_<quality>`

**Common Options:**

| Option | SDK Equivalent    | Description                                       |
|--------|-------------------|---------------------------------------------------|
| `f`    | `format` (string) | Target format. The current service behavior maps this to a plain segment such as `image/format,webp`. Common values: `jpg`, `png`, `webp`. |
| `q`    | `quality` (int)   | Quality for lossy formats (e.g., 1-100 for JPG).  |

**Example `process` string:** `"image/format,webp,q_85"`

### 3. `ImageResize`

Resizes an image with various scaling options.

**Process String:** `image/resize,w_<width>,h_<height>,m_<mode>`

**Common Options:**

| Option | SDK Equivalent | Description                                                               |
|--------|----------------|---------------------------------------------------------------------------|
| `w`    | `width` (int)  | Target width in pixels.                                                   |
| `h`    | `height` (int) | Target height in pixels.                                                  |
| `m`    | `mode` (string)| Resize mode (e.g., `lfit`, `mfit`, `fill`, `fixed`). See official docs for all modes. |

**Example `process` string:** `"image/resize,w_800,m_lfit"` (Resize to width 800, maintain aspect ratio)

### 4. `ImageDraw`

Draws points and optional connecting lines directly on the image.

**Process String:** `image/draw,p_<points>,r_<radius>,l_<true|false>,lw_<line_width>,color_<RRGGBB>`

**Common Options:**

| Option | Meaning | Example |
|--------|---------|---------|
| `p` | Point list formatted as `x1xy1-x2xy2-...` | `50x50-200x120-320x220` |
| `r` | Point radius in pixels | `r_6` |
| `l` | Whether to connect points with lines | `l_true` |
| `lw` | Line width in pixels | `lw_3` |
| `color` | RGB hex color | `color_FF0000` |

**Example `process` string:** `"image/draw,p_50x50-200x120-320x220,r_6,l_true,lw_3,color_FF0000"`

### 5. `ImageZoom`

This is a script-level pattern rather than a standalone server primitive. The helper composes:

1. `image/resize,...`
2. `/crop,...`

to create a zoom-like final image focused on a target region.

**Example `process` string:** `"image/resize,w_1200,m_fill/crop,w_500,h_400,g_center"`

### 6. `ImageWatermark`

Applies a visible watermark (text or image) to the image. The parameter set is extensive.

**Process String:** `image/watermark,<param1>_<value1>,<param2>_<value2>,...`

**Conceptual Parameters (refer to official docs for actual keys and values):**

- `text`: Text watermark content. **Value must be URL-safe Base64 encoded.**
- `type`: Text watermark font. **Value must be URL-safe Base64 encoded.**
- `color`: Text color in `RRGGBB`.
- `size`: Text size in px.
- `shadow`: Shadow opacity in `[0,100]`.
- `rotate`: Clockwise rotation angle in `[0,360]`.
- `fill`: Whether to tile text watermark across the full image: `0` or `1`.
- `image`: Watermark image reference in the same bucket. **Value must be URL-safe Base64 encoded.** If preprocessing is needed, encode the full watermark reference string including `?x-tos-process=...`.
- `t`: Watermark opacity in `[0,100]`.
- `g`: Placement. Common values: `nw`, `north`, `ne`, `west`, `center`, `east`, `sw`, `south`, `se`.
- `x`/`y`: Horizontal and vertical margins in px.
- `voffset`: Vertical offset from the center line.
- `order` / `align` / `interval`: Mixed text+image watermark layout controls.

**Example `process` string:** `"image/watermark,text_SGVsbG8,type_ZmFuZ3poZW5nc2h1c29uZw,color_FF0000,size_72,g_center,rotate_45"`

### 7. `ImageBlindWatermark`

Adds a blind (invisible) watermark to an image.

**Process String:** `image/blindwatermark,<param1>_<value1>,...`

**Conceptual Parameters (refer to official docs):**

- `text`: Watermark text content to embed.
- Other parameters as documented by the official TOS blind watermark API.

**Prerequisites:**
- The blind watermark capability must be **enabled at the account/bucket level** in the TOS console.
- The source image must be at least **512×512 pixels**.

**Behavior Notes:**
- If the capability is not enabled, `scripts/image_blindwatermark.py` prints `[SKIP]` and exits successfully by default. Use `--strict` to make this a hard failure.
- If the image is smaller than 512×512, the script prints a clear error message with the actual image dimensions and the minimum requirement.

### 8. `ImageProcess` (Generic)

This is not a specific operation but a generic entry point to use any process string. It allows for combining operations or using newly introduced features not explicitly covered by the other scripts.

**Example `process` string (chaining resize and format):** `"image/resize,w_500|image/format,png"` (Syntax may vary, check official docs for chaining rules).

---

### 9. `ImageUnderstanding`

AI-powered image understanding via VLM (Vision Language Model). Supports description, OCR, face detection, and any visual Q&A through natural language prompts.

**SDK Method:** `client.get_object()` with `request_timeout=120`

**Key Parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `bucket` | string | Yes | The bucket containing the image. |
| `key` | string | Yes | The object key of the image. |
| `process` | string | Yes | Constructed as `image/understanding,m_<b64_model>,p_<b64_prompt>` |
| `save_bucket` | string | No | Base64-encoded destination bucket for saving result. |
| `save_object` | string | No | Base64-encoded destination object key for saving result. |

**Constructing the `process` Parameter:**

The `m` (model) and `p` (prompt) values must be **URL-Safe Base64 encoded with `=` padding removed**:

```python
import base64

model = "doubao-seed-1.6-vision"
prompt = "Describe this image"

model_b64 = base64.urlsafe_b64encode(model.encode()).decode().rstrip("=")
prompt_b64 = base64.urlsafe_b64encode(prompt.encode()).decode().rstrip("=")

process_str = f"image/understanding,m_{model_b64},p_{prompt_b64}"
```

**Optional `d` parameter:** Detail level — `auto`, `low`, or `high`. Append `,d_high` to the process string.

**CLI Mapping:**

| CLI argument | Meaning | Notes |
|---|---|---|
| `--key` | Source image object key | Required |
| `--prompt` | Natural language prompt | Required |
| `--model` | VLM model name | Default `doubao-seed-1.6-vision` |
| `--detail` | Detail level | `auto`/`low`/`high`; optional |
| `--output` | Local output file | Optional |
| `--saveas-bucket` | Save result to TOS bucket | Optional |
| `--saveas-object` | Save result as TOS object key | Optional |

**Response Format:**

```json
{
  "content": "The image features a cute plush toy..."
}
```

**Important Notes:**
- Response time is typically 10-60 seconds. Set `request_timeout=120` on the client.
- Requires account whitelist. If not whitelisted, returns `"The account: xxx is not in the whitelist."`
- Image must meet minimum size requirements (width/height/pixels).

**Script:** `scripts/image_understanding.py`

---

## Data Models

### ImageInfo Object

A JSON object containing detailed information about the image, when `image/info` returns structured metadata.

| Field       | Type   | Description                                   |
|-------------|--------|-----------------------------------------------|
| `Format`    | string | The format of the image (e.g., "jpeg", "png"). |
| `ImageWidth`| int    | The width of the image in pixels.             |
| `ImageHeight`| int   | The height of the image in pixels.            |
| `FileSize`  | int    | The size of the image file in bytes.          |
| `Orientation`| int   | The EXIF orientation tag.                     |
| `...`       | ...    | Other fields may be present (e.g., EXIF data).|

If the service returns raw bytes instead of JSON, the helper script prints a fallback object shaped like:

```json
{
  "source": "fallback-local-parse",
  "format": "jpeg",
  "bytes": 214513,
  "width": 640,
  "height": 427
}
```

**Example Snippet:**
```json
{
  "FileSize": {
    "Value": "102400"
  },
  "Format": {
    "Value": "jpeg"
  },
  "ImageHeight": {
    "Value": "800"
  },
  "ImageWidth": {
    "Value": "1200"
  }
}
```

### ProcessSaveResult Object

A JSON object returned when an image processing operation is successfully saved directly to TOS using the `save_bucket` and `save_object` parameters.

| Field           | Type   | Description                                           |
|-----------------|--------|-------------------------------------------------------|
| `ETag`          | string | The ETag of the saved object.                         |
| `Bucket`        | string | The bucket where the result was saved.                |
| `Object`        | string | The object key of the saved result.                   |
| `VersionId`     | string | The version ID if the bucket has versioning enabled.  |
| `HashCrc64ecma` | string | The CRC64 checksum of the object.                     |
