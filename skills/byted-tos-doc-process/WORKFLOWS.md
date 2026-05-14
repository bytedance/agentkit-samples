# Bytedance TOS Document Process Workflows

This document illustrates common workflows for document processing using the `doc-preview` feature via **pre-signed URLs** with the Volcengine TOS Python SDK.

## Table of Contents
- [Workflow 1: Previewing a Document as a Single PDF](#workflow-1-previewing-a-document-as-a-single-pdf)
- [Workflow 2: Previewing a Specific Page as a PNG Image](#workflow-2-previewing-a-specific-page-as-a-png-image)
- [Workflow 3: Getting the HTML Preview URL](#workflow-3-getting-the-html-preview-url)
- [Workflow 4: Batch Exporting a Page Range to TOS](#workflow-4-batch-exporting-a-page-range-to-tos)
- [Workflow 5: Batch Screenshot a PDF Page Range](#workflow-5-batch-screenshot-a-pdf-page-range)
- [Workflow 6: Reading the Total Page Count Header](#workflow-6-reading-the-total-page-count-header)
- [Workflow 7: Handling Errors](#workflow-7-handling-errors)
- [Workflow 8: Document to Image Set Pipeline (Orchestration)](#workflow-8-document-to-image-set-pipeline-orchestration)

---

### Prerequisite: Client Initialization

All workflows assume you have a `tos.TosClientV2` instance initialized. See `README.md` for details.

```python
import os
import tos
from tos.enum import HttpMethodType
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from doc_preview_params import build_doc_preview_query_params

# ... (create_client function)
client = create_client()
bucket_name = os.getenv("TOS_BUCKET")
object_key = os.getenv("TOS_OBJECT_KEY")
```

---

### Workflow 1: Previewing a Document as a Single PDF

**Goal**: Convert a DOCX, PPTX, or other office document into a single PDF file and save it locally.

**Script**: `scripts/doc_preview_pdf.py`

**Steps**:
1.  Build query parameters for PDF preview using `build_doc_preview_query_params`.
2.  Generate a pre-signed URL with `client.pre_signed_url()`.
3.  Use `urllib.request.urlopen` to download the content from the signed URL and save it to a file.

**Python Example (`scripts/doc_preview_pdf.py` logic):**
```python
# Assumes 'client', 'bucket_name', 'object_key' are initialized
output_pdf_path = "document_preview.pdf"

try:
    print(f"Converting {bucket_name}/{object_key} to PDF -> {output_pdf_path}...")
    
    params = build_doc_preview_query_params(dest_type="pdf")
    presigned = client.pre_signed_url(HttpMethodType.Http_Method_Get, bucket_name, object_key, query=params)
    req = Request(presigned.signed_url, headers=presigned.signed_header)
    
    with urlopen(req) as response, open(output_pdf_path, "wb") as f_out:
        f_out.write(response.read())

    print(f"Successfully saved PDF to {output_pdf_path}")
except (HTTPError, URLError, tos.exceptions.TosServerError) as e:
    print(f"Error during PDF conversion: {e}")
```

---

### Workflow 2: Previewing a Specific Page as a PNG Image

**Goal**: Generate a high-quality PNG image of the 5th page of a document.

**Script**: `scripts/doc_preview_png.py`

**Steps**:
1.  Build query parameters, specifying `dest_type="png"`, `page=5`, and optional `image_dpi`.
2.  Generate and use the pre-signed URL to download the image.

**Python Example (`scripts/doc_preview_png.py` logic):**
```python
page_to_preview = 5
output_image_path = f"page_{page_to_preview}.png"

try:
    params = build_doc_preview_query_params(
        dest_type="png",
        page=page_to_preview,
        image_dpi=200
    )
    presigned = client.pre_signed_url(HttpMethodType.Http_Method_Get, bucket_name, object_key, query=params)
    req = Request(presigned.signed_url, headers=presigned.signed_header)
    
    with urlopen(req) as response, open(output_image_path, "wb") as f_out:
        f_out.write(response.read())
        
    print(f"Successfully saved page {page_to_preview} to {output_image_path}")
except Exception as e:
    print(f"Error during PNG conversion: {e}")
```

---

### Workflow 3: Getting the HTML Preview URL

**Goal**: Obtain the final, accessible URL for an HTML-based document preview.

**Script**: `scripts/doc_preview_html_url.py`

**Steps**:
1.  Generate a pre-signed URL with `dest_type="html"`.
2.  Fetch the temporary HTML content from this URL.
3.  Parse the HTML to find the `token` value.
4.  URL-safe Base64 decode the token to get the final preview URL.

**Python Example (`scripts/doc_preview_html_url.py` logic):**
```python
import base64

try:
    params = build_doc_preview_query_params(dest_type="html")
    presigned = client.pre_signed_url(HttpMethodType.Http_Method_Get, bucket_name, object_key, query=params)
    req = Request(presigned.signed_url, headers=presigned.signed_header)

    with urlopen(req) as response:
        html_content = response.read().decode('utf-8')
    
    # ... logic to extract and decode token ...
    # final_url = decode_preview_url(token)
    
    # print(f"Successfully extracted HTML preview URL: {final_url}")
    
except Exception as e:
    print(f"An error occurred while getting HTML preview URL: {e}")
```

---

### Workflow 4: Batch Exporting a Page Range to TOS

**Goal**: Convert pages 1 through 5 of a document into JPG images and save them directly into a destination bucket in TOS.

**Script**: `scripts/doc_preview_process.py`

```bash
python3 scripts/doc_preview_process.py \
  --key report.docx \
  --dest-type jpg \
  --img-mode 1 \
  --start-page 1 \
  --end-page 5 \
  --saveas-bucket my-output-bucket \
  --saveas-object processed/{Page}.jpg \
  --json
```

**Behavior Notes**:
- `--json` returns a structured payload for downstream agent steps.
- `--dry-run` prints the resolved `x-tos-doc-*` parameters without making the request.
- Without save-as parameters, the script writes the converted output locally.

---

### Workflow 5: Batch Screenshot a PDF Page Range

**Goal**: Export multiple PDF pages to TOS as image objects with one request.

**Script**: `scripts/doc_batch_screenshot.py`

```bash
python3 scripts/doc_batch_screenshot.py \
  --key test.pdf \
  --format png \
  --start-page 1 \
  --end-page 2 \
  --saveas-object "skill-test/doc/{Page}.png"
```

**Important constraints**:
- Source object must be a PDF.
- Destination object must contain `{Page}`.
- Results are always persisted back to TOS via `--saveas-bucket` / `--saveas-object`.
- The helper handles save-as query encoding automatically.

---

### Workflow 6: Reading the Total Page Count Header

**Goal**: Efficiently determine the number of pages in a document.

**Script**: `scripts/doc_total_page.py`

```bash
python3 scripts/doc_total_page.py --key report.docx --dest-type pdf --json
python3 scripts/doc_total_page.py --key report.docx --dest-type pdf --dry-run
```

**Behavior Notes**:
- `--json` returns a structured payload with the resolved query params and `total_page` when available.
- `--dry-run` prints the resolved request without issuing the HTTP call.
- If the header is absent, the script returns a warning payload instead of crashing.

---

### Workflow 7: Validate a doc-preview Request Before Execution

**Goal**: Let an agent inspect the resolved `doc-preview` parameters before downloading or exporting.

```bash
python3 scripts/doc_preview_process.py \
  --key report.docx \
  --dest-type png \
  --page 2 \
  --dry-run
```

**Behavior Notes**:
- Useful for agent planning when the next step depends on resolved `x-tos-doc-*` parameters.
- Combine with `--json` for machine-readable planning output.

---

### Workflow 8: Handling Errors

**Goal**: Gracefully handle common errors during the process.

**Strategy**:
- Wrap pre-signed URL generation in a `try...except` block for `TosServerError` and `TosClientError`.
- Wrap HTTP requests (`urlopen`) in a `try...except` block for `HTTPError` and `URLError`.

**Python Example:**
```python
try:
    # ... build params ...
    presigned = client.pre_signed_url(...)
    req = Request(presigned.signed_url, headers=presigned.signed_header)
    
    with urlopen(req) as response:
        # ... process response ...
        
except tos.exceptions.TosServerError as e:
    print(f"TOS SDK Error: {e.message}")
except HTTPError as e:
    print(f"HTTP Error: Status {e.code}, Reason: {e.reason}")
except URLError as e:
    print(f"URL Error: {e.reason}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
```
This ensures that failures from both the SDK and the subsequent HTTP call are caught and reported.

---

### Workflow 8: Document to Image Set Pipeline (Orchestration)

**Goal**: Convert a document (docx/pptx/xlsx) into a set of page images packaged as a zip archive — a multi-step, multi-skill pipeline an agent can orchestrate.

**Pipeline**: `doc_total_page` → `doc_preview_process` (docx→PDF) → `doc_batch_screenshot` (PDF→JPG) → `file_compress` (JPG→zip)

**Skills involved**: `byted-tos-doc-process`, `byted-tos-file-process`

**Important constraints**:
- `doc_batch_screenshot` only accepts **PDF** as the source file (backend restriction). Non-PDF documents (docx, pptx, etc.) must be converted to PDF first.
- The sync `doc-preview` + `save-as` mode does not reliably persist PDF output to TOS. Use local download + upload instead.

#### Step 1: Get total page count

```bash
python3 scripts/doc_total_page.py --key report.docx --dest-type pdf --json
```

Extract `total_page` from the JSON output to determine the page range.

#### Step 2: Convert document to PDF locally, then upload

```bash
# Download PDF to local filesystem
python3 scripts/doc_preview_process.py \
  --key report.docx \
  --dest-type pdf \
  --output /tmp/report.pdf

# Upload PDF to TOS for batch screenshot input
# (Use TOS SDK put_object or any upload method)
```

**Note**: The sync `doc-preview` + `save-as-bucket`/`save-as-object` mode returns PDF binary in the response body but may not correctly persist it to TOS. Downloading locally and uploading is the reliable approach.

#### Step 3: Batch screenshot all pages

```bash
python3 scripts/doc_batch_screenshot.py \
  --key path/to/report.pdf \
  --format jpg \
  --start-page 1 \
  --end-page 14 \
  --saveas-bucket my-bucket \
  --saveas-object "output/pages/{Page}.jpg"
```

This produces one JPG per page in TOS. The `{Page}` placeholder is required.

#### Step 4: Compress page images into a zip

```bash
python3 /path/to/byted-tos-file-process/scripts/file_compress.py \
  --keys output/pages/1.jpg,output/pages/2.jpg,...,output/pages/14.jpg \
  --format zip \
  --saveas-bucket my-bucket \
  --saveas-object output/pages.zip \
  --wait --json
```

The final result is a single zip archive containing all page images.

#### Agent orchestration notes

- Step 1 determines the page range; the agent should use the `total_page` value for `--end-page` and to build the `--keys` list in Step 4.
- Step 2 requires an intermediate upload not covered by this skill alone — the agent should use the TOS SDK or another upload method.
- Step 3 depends on Step 2 (PDF must exist in TOS before batch screenshot).
- Step 4 depends on Step 3 (all page images must exist before compression).
