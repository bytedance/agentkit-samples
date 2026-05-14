# Bytedance TOS Image Process Workflows

This document illustrates common end-to-end workflows for image processing using the TOS Python SDK and the scripts provided in this skill.

## Table of Contents
- [Workflow 1: Getting Image Information](#workflow-1-getting-image-information)
- [Workflow 2: Resizing an Image and Saving Locally](#workflow-2-resizing-an-image-and-saving-locally)
- [Workflow 3: Converting Format and Saving back to TOS](#workflow-3-converting-format-and-saving-back-to-tos)
- [Workflow 4: Drawing Points and Lines](#workflow-4-drawing-points-and-lines)
- [Workflow 5: Creating a Zoom Crop](#workflow-5-creating-a-zoom-crop)
- [Workflow 6: Applying a Text Watermark](#workflow-6-applying-a-text-watermark)
- [Workflow 7: Batch Processing Multiple Images](#workflow-7-batch-processing-multiple-images)
- [Workflow 8: Handling Errors](#workflow-8-handling-errors)
- [Workflow 9: AI-Powered Image Understanding](#workflow-9-ai-powered-image-understanding)
- [Workflow 10: Smart Annotation Pipeline (Orchestration)](#workflow-10-smart-annotation-pipeline-orchestration)

---

### Workflow 1: Getting Image Information

**Goal**: Retrieve the metadata (format, dimensions, etc.) of an image stored in TOS.

**Script**: `scripts/image_info.py`

1.  **Set Environment**:
    ```bash
    export TOS_ACCESS_KEY="YOUR_AK"
    export TOS_SECRET_KEY="YOUR_SK"
    export TOS_ENDPOINT="https://tos-cn-beijing.volces.com"
    export TOS_REGION="cn-beijing"
    export TOS_BUCKET="my-source-bucket"
    export TOS_OBJECT_KEY="images/archive/photo-01.jpg"
    ```

2.  **Execute**:
    ```bash
    python3 scripts/image_info.py --key images/archive/photo-01.jpg --json
    ```

3.  **Behavior Notes**:
    - `--bucket` / `--key` override environment defaults.
    - `--json` returns a machine-readable payload.
    - If `image/info` returns raw bytes rather than JSON, the script falls back to local parsing and reports basic metadata.

---

### Workflow 2: Resizing an Image and Saving Locally

**Goal**: Resize an image to a 500-pixel width and save the result to the local filesystem.

**Script**: `scripts/image_resize.py`

1.  **Set Environment**: (Same as Workflow 1)

2.  **Execute**:
    ```bash
    python3 scripts/image_resize.py --key images/archive/photo-01.jpg --w 500 --output resized_local.jpg --dry-run
    python3 scripts/image_resize.py --key images/archive/photo-01.jpg --w 500 --output resized_local.jpg
    ```

3.  **Behavior Notes**:
    - `--dry-run` prints the resolved process and output target before calling TOS.
    - `--json` returns a machine-readable payload for either local save or TOS persistence mode.

---

### Workflow 3: Converting Format and Saving back to TOS

**Goal**: Convert an image to WebP format with 80% quality and save it to another location in TOS.

**Script**: `scripts/image_format.py`

1.  **Set Environment**: (Same as Workflow 1)

2.  **Execute**:
    ```bash
    python3 scripts/image_format.py \
      --key images/archive/photo-01.jpg \
      --f webp \
      --q 80 \
      --saveas-bucket my-output-bucket \
      --saveas-object processed/photo-01.webp \
      --json
    ```

3.  **Behavior Notes**:
    - `--saveas-bucket` / `--saveas-object` switch the script into TOS-to-TOS mode.
    - `--json` returns a structured payload including the resolved process string and TOS save result.
    - `--dry-run` prints the resolved request without calling TOS.

---

### Workflow 4: Drawing Points and Lines

**Goal**: Mark several points and connect them with lines so an agent can highlight positions of interest.

**Script**: `scripts/image_draw.py`

```bash
# Draw a polyline (open path)
python3 scripts/image_draw.py \
  --key test.jpg \
  --points 50x50-200x120-320x220 \
  --line \
  --color FF0000 \
  --output draw.jpg
```

**Note**: `--line` connects points in order but does **not** auto-close. To draw a closed rectangle, repeat the first point at the end:

```bash
# Draw a closed rectangle: A-B-C-D-A
python3 scripts/image_draw.py \
  --key test.jpg \
  --points 100x100-400x100-400x300-100x300-100x100 \
  --line \
  --line-width 3 \
  --color FF0000 \
  --saveas-bucket my-bucket \
  --saveas-object output/boxed.jpg
```

---

### Workflow 5: Creating a Zoom Crop

**Goal**: First enlarge the source view and then crop a focused center region.

**Script**: `scripts/image_zoom.py`

```bash
python3 scripts/image_zoom.py \
  --key test.jpg \
  --resize-w 1200 \
  --crop-w 500 \
  --crop-h 400 \
  --gravity center \
  --output zoom.jpg
```

---

### Workflow 6: Applying a Text Watermark

**Goal**: Add a semi-transparent text watermark to the bottom-right corner of an image.

**Script**: `scripts/image_watermark.py`

1.  **Set Environment**: (Same as Workflow 1)

2.  **Prepare Parameters**: Watermark text and colors must be Base64-encoded.
    The helper script can encode raw text and font names for you, so you can usually provide readable values directly.

3.  **Execute**:
    ```bash
    python3 scripts/image_watermark.py \
      --text "2026 MyCorp" \
      --font fangzhengshusong \
      --color FF0000 \
      --size 72 \
      --gravity se \
      --x 20 \
      --y 20 \
      --output "watermarked.jpg"
    ```
    *Note: For pre-encoded official values, you can switch to `--text-b64`, `--font-b64`, and `--image-b64`.*

4.  **SDK Logic (`image_watermark.py`)**:
    ```python
    # Constructs the process string from the official watermark model
    process_rule = "image/watermark,text_MjAyNiBNeUNvcnA,type_ZmFuZ3poZW5nc2h1c29uZw,color_FF0000,size_72,g_se,x_20,y_20"
    
    client.get_object_to_file(
        bucket=...,
        key=...,
        file_path="watermarked.jpg",
        process=process_rule
    )
    ```

---

### Workflow 6A: Applying a Blind Watermark

**Goal**: Embed a blind watermark when the capability is enabled for the current account or bucket.

**Script**: `scripts/image_blindwatermark.py`

**Prerequisites**:
- Blind watermark capability must be enabled in the TOS console.
- The source image must be at least **512×512 pixels**.

1.  **Execute**:
    ```bash
    python3 scripts/image_blindwatermark.py \
      --kv text=HelloBlind \
      --output "blindwatermarked.jpg"
    ```

2.  **Behavior Notes**:
    - If the capability is enabled and the image is large enough, the script saves the output and prints `[OK]`.
    - If the capability is not enabled, the script prints `[SKIP]` and exits successfully by default. Add `--strict` to fail the command instead.
    - If the image is smaller than 512×512 pixels, the script prints a clear error message and exits with code 1.

---

### Workflow 7: Batch Processing Multiple Images

**Goal**: Resize a list of images from a source folder in TOS to a destination folder.

**This requires a custom script that iterates and calls the SDK.**

1.  **Set Environment**: (Same as Workflow 1, but `TOS_OBJECT_KEY` is not used).

2.  **Custom Batch Script (Conceptual)**:
    ```python
    import os
    import tos

    # Assumes client is initialized
    
    source_bucket = "my-source-bucket"
    dest_bucket = "my-output-bucket"
    image_keys = ["source/img1.jpg", "source/img2.jpg", "source/img3.jpg"]
    
    for key in image_keys:
        dest_key = key.replace("source/", "resized/")
        print(f"Processing {source_bucket}/{key} -> {dest_bucket}/{dest_key}")
        
        try:
            client.get_object(
                bucket=source_bucket,
                key=key,
                process="image/resize,w_1200",
                save_bucket=dest_bucket,
                save_object=dest_key
            )
        except tos.exceptions.TosServerError as e:
            print(f"  [ERROR] Failed for {key}: {e.message}")
    
    print("Batch processing complete.")
    ```

---

### Workflow 8: Handling Errors

**Goal**: Gracefully handle potential errors from the TOS SDK.

All provided scripts include `try...except` blocks to catch `TosServerError` and `TosClientError`.

**SDK Logic**:
```python
try:
    # ... SDK call ...
    client.get_object(bucket="non-existent-bucket", key="invalid-key", process="image/info")

except tos.exceptions.TosServerError as e:
    # For server-side errors (e.g., object not found, invalid parameters)
    print(f"TOS Server Error:")
    print(f"  - Status: {e.status_code}")
    print(f"  - Code: {e.code}")
    print(f"  - Message: {e.message}")
    print(f"  - Request ID: {e.request_id}")
    sys.exit(1)

except tos.exceptions.TosClientError as e:
    # For client-side issues (e.g., network error, invalid credentials)
    print(f"TOS Client Error: {e}")
    sys.exit(1)
```
This ensures that failures are caught and reported with meaningful diagnostic information, such as the `request_id`, which is crucial for troubleshooting with support teams.

---

### Workflow 9: AI-Powered Image Understanding

**Goal**: Use a VLM (Vision Language Model) to understand image content — describe, OCR, detect faces, or answer visual questions.

**Script**: `scripts/image_understanding.py`

1. **Set Environment**: (Same as Workflow 1)

2. **Execute (describe image)**:
   ```bash
   python3 scripts/image_understanding.py \
     --key photo.jpg \
     --prompt "Describe this image in detail"
   ```

3. **Execute (OCR)**:
   ```bash
   python3 scripts/image_understanding.py \
     --key document.png \
     --prompt "识别图片中的所有文字内容"
   ```

4. **Execute (save result to TOS)**:
   ```bash
   python3 scripts/image_understanding.py \
     --key photo.jpg \
     --prompt "What objects are in this image?" \
     --saveas-bucket my-output-bucket \
     --saveas-object results/understanding.json
   ```

5. **Behavior Notes**:
   - The `--prompt` parameter is required. It accepts any natural language question or instruction.
   - Default model is `doubao-seed-1.6-vision`. Override with `--model`.
   - `--json` returns a machine-readable payload. `--dry-run` prints the resolved process string before execution.
   - Response time is typically 10-60 seconds due to VLM inference.
   - Requires account whitelist. If not whitelisted, the script will return an error.
   - The result is a JSON object with a `content` field containing the model's response.

---

### Workflow 10: Smart Annotation Pipeline (Orchestration)

**Goal**: Automatically understand an image and produce an annotated, watermarked result — a multi-step pipeline an agent can orchestrate.

**Pipeline**: `image_info` → `image_understanding` → `image_draw` → `image_watermark`

#### Step 1: Get image dimensions

```bash
python3 scripts/image_info.py --key test.jpg --json
```

Use the returned `ImageWidth` and `ImageHeight` to decide annotation coordinates for the next steps.

#### Step 2: Understand image content with VLM

```bash
python3 scripts/image_understanding.py \
  --key test.jpg \
  --prompt "请描述这张图片的内容，包括场景、主体物体和氛围" \
  --json
```

The `content` field contains the model's description. Use this to decide what label to draw and where to place the bounding box.

#### Step 3: Draw a bounding box around the subject

```bash
python3 scripts/image_draw.py \
  --key test.jpg \
  --points 200x80-520x80-520x380-200x380-200x80 \
  --line \
  --line-width 3 \
  --color FF0000 \
  --saveas-bucket my-bucket \
  --saveas-object smart-annotate/boxed.jpg
```

**Important**: Repeat the first point at the end to close the rectangle (the `--line` flag does not auto-close).

#### Step 4: Add a text label as watermark

```bash
python3 scripts/image_watermark.py \
  --key smart-annotate/boxed.jpg \
  --text "Go Gopher" \
  --font wqy-zenhei \
  --color FFFFFF \
  --size 30 \
  --opacity 80 \
  --gravity nw \
  --x 10 \
  --y 10 \
  --saveas-bucket my-bucket \
  --saveas-object smart-annotate/final.jpg \
  --json
```

The final result is a single image with a red bounding box around the detected subject and a text label in the corner.

#### Agent orchestration notes

- All steps support `--json` for machine-readable output, making it easy for an agent to parse results and feed them into the next step.
- Use `--dry-run` on any step to preview the resolved request before execution.
- Step 3 depends on Step 1 (image dimensions) and Step 2 (content understanding) to determine coordinates and label text. An agent should extract `ImageWidth`/`ImageHeight` from Step 1 and `content` from Step 2, then compute bounding box coordinates accordingly.
