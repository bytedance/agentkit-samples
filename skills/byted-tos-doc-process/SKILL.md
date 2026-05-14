---
name: byted-tos-doc-process
description: "Previews and exports documents stored in Volcengine TOS: generate PDF/PNG/JPG previews, read page counts, resolve HTML preview URLs, and batch-export PDF pages as images. Use this skill when the user needs to convert or preview office documents (Word, Excel, PPT, PDF), export specific pages as images, get document page counts, or generate HTML preview links — even if they don't explicitly mention 'doc-preview' or 'document conversion'."
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
user-invocable: true
license: Apache-2.0
---

# Volcengine TOS Document Process

Preview and convert office documents stored in Volcengine TOS — PDF/PNG/JPG conversion, page count, HTML preview URL, and page-range export.

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
| `TOS_BUCKET` | Yes | Source bucket that stores the document |
| `TOS_OBJECT_KEY` | No | Source object key of the document. Can be overridden with `--key` |
| `TOS_SECURITY_TOKEN` | No | STS session token when using temporary credentials |

## Quick start (common tasks)

```bash
# Convert document to PDF
python3 {baseDir}/scripts/doc_preview_pdf.py --key report.docx --output preview.pdf

# Preview page 2 as PNG
python3 {baseDir}/scripts/doc_preview_png.py --key report.docx --page 2 --output page_2.png

# Preview page 2 as JPG
python3 {baseDir}/scripts/doc_preview_jpg.py --key report.docx --page 2 --output page_2.jpg

# Get total page count
python3 {baseDir}/scripts/doc_total_page.py --key report.docx --dest-type pdf

# Resolve HTML preview URL
python3 {baseDir}/scripts/doc_preview_html_url.py --key report.docx

# Batch export page range to TOS
python3 {baseDir}/scripts/doc_preview_process.py --key report.docx \
  --dest-type jpg --img-mode 1 --start-page 1 --end-page 3 \
  --saveas-bucket "output-bucket" --saveas-object "export/page_{Page}.jpg"

# Batch screenshot a PDF page range
python3 {baseDir}/scripts/doc_batch_screenshot.py --key test.pdf \
  --format png --start-page 1 --end-page 3 \
  --saveas-object "skill-test/doc/{Page}.png"
```

## Available scripts

| Script | Purpose |
|--------|---------|
| `scripts/doc_preview_pdf.py` | Convert document to PDF and save locally. |
| `scripts/doc_preview_png.py` | Render a single page as PNG. |
| `scripts/doc_preview_jpg.py` | Render a single page as JPG. |
| `scripts/doc_total_page.py` | Read total page count via `x-tos-total-page` header. |
| `scripts/doc_preview_html_url.py` | Resolve the final HTML preview URL (follows redirects and extracts tokens). |
| `scripts/doc_preview_process.py` | Generic doc-preview with full parameter control; supports TOS-to-TOS export. |
| `scripts/doc_preview_params.py` | Helper library to build `x-tos-doc-*` query parameters consistently. |
| `scripts/doc_batch_screenshot.py` | Batch-export PDF pages as images through doc-preview batch mode. |

All scripts support `--key` to override `TOS_OBJECT_KEY`. Structured scripts also support `--json` for machine-readable output, and `doc_preview_process.py` / `doc_total_page.py` support `--dry-run` to preview the resolved request. Run any script with `-h` for full usage.

## Out of scope

- Editing document contents (this skill is read-only preview/conversion).
- Generic object storage tasks unrelated to document preview.
- Local office conversion workflows that do not involve TOS.

## Rules

- **Authentication**: Authentication is provided by the TOS identity declared in the `metadata` block above. Object selection can be overridden per script with `--key`.
- **Pre-signed URL pattern**: Document preview uses pre-signed URLs with `x-tos-process=doc-preview` and `x-tos-doc-*` query parameters, not the direct `process` keyword of `get_object`. Use `doc_preview_params.py` to build parameters consistently.
- **Batch screenshot constraint**: `doc_batch_screenshot.py` currently requires a PDF source object and persists results back to TOS with a `{Page}` placeholder.
- **Save-as encoding**: For `doc-preview` query-based save-as, the helper script automatically URL-safe-Base64 encodes `x-tos-save-bucket` and `x-tos-save-object` to match backend expectations.
- **Custom domain note**: For buckets created after Jan 03, 2024, online HTML preview may require a custom domain rather than the default TOS domain.
- **Parameter source of truth**: Official Volcengine TOS documentation is authoritative for the full `doc-preview` parameter matrix. When uncertain, check [REFERENCE.md](REFERENCE.md).
- **Language**: Reply in the user's preferred language.

## Further reading

- Setup and environment: [README.md](README.md)
- Parameter reference: [REFERENCE.md](REFERENCE.md)
- End-to-end workflows: [WORKFLOWS.md](WORKFLOWS.md)
