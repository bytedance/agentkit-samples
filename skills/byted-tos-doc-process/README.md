# Bytedance TOS Document Process Skill

This skill provides a polished document-processing toolkit for files stored in Bytedance TOS. It covers synchronous `doc-preview` flows for format conversion, page preview, and batch export.

## When To Use

Use this skill when you need to:
- Convert office documents in TOS to `pdf`, `png`, `jpg`, or `html`
- Preview a single page as an image
- Read document page count from `x-tos-total-page`
- Export a page range back to another TOS location
- Batch screenshot PDF pages to TOS
- Debug or construct `doc-preview` requests and `x-tos-doc-*` parameters

Do not use this skill for:
- Editing document contents
- Generic object storage tasks unrelated to document preview
- Local office conversion workflows that do not involve TOS

## Why This Skill Exists

The Volcengine TOS Python SDK supports object processing, but document-specific preview parameters are not exposed as direct `get_object(...)` keyword arguments. For `doc-preview`, the reliable pattern is:

1. Build the required `x-tos-process` and `x-tos-doc-*` query parameters.
2. Generate a pre-signed URL with `pre_signed_url(...)`.
3. Fetch the processed result over HTTP.

That pattern is the core of this skill.

## Directory Layout

```text
byted-tos-doc-process/
├── SKILL.md
├── README.md
├── REFERENCE.md
├── WORKFLOWS.md
├── LICENSE
├── requirements.txt
└── scripts/
    ├── doc_preview_params.py
    ├── doc_preview_pdf.py
    ├── doc_preview_png.py
    ├── doc_preview_jpg.py
    ├── doc_preview_html_url.py
    ├── doc_preview_process.py
    ├── doc_total_page.py
    └── doc_batch_screenshot.py
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
| `TOS_BUCKET` | Yes | Source bucket that stores the document. | `my-doc-bucket` |
| `TOS_OBJECT_KEY` | Yes | Source object key of the document. | `reports/q1-review.docx` |
| `TOS_SECURITY_TOKEN` | No | STS session token when using temporary credentials. | `STS...` |

For production usage, prefer short-lived STS credentials. The SDK automatically uses `TOS_SECURITY_TOKEN` when it is present.

## Quick Start

Export the minimum required configuration:

```bash
export TOS_ACCESS_KEY="YOUR_AK"
export TOS_SECRET_KEY="YOUR_SK"
export TOS_ENDPOINT="https://tos-cn-beijing.volces.com"
export TOS_REGION="cn-beijing"
export TOS_BUCKET="your-doc-bucket"
export TOS_OBJECT_KEY="path/to/your/document.docx"
```

Run one of the ready-to-use examples:

Convert to PDF:

```bash
python3 scripts/doc_preview_pdf.py --output preview.pdf
```

Preview page 2 as PNG:

```bash
python3 scripts/doc_preview_png.py --page 2 --output page_2.png
```

Preview page 2 as JPG:

```bash
python3 scripts/doc_preview_jpg.py --page 2 --output page_2.jpg
```

Resolve the final HTML preview URL:

```bash
python3 scripts/doc_preview_html_url.py
```

Read total page count:

```bash
python3 scripts/doc_total_page.py --dest-type pdf --json
```

Batch export a page range to TOS:

```bash
python3 scripts/doc_preview_process.py \
  --dest-type jpg \
  --img-mode 1 \
  --start-page 1 \
  --end-page 3 \
  --saveas-bucket "your-output-bucket" \
  --saveas-object "export/page_{Page}.jpg"
```

Batch screenshot a PDF page range:

```bash
python3 scripts/doc_batch_screenshot.py \
  --key test.pdf \
  --format png \
  --start-page 1 \
  --end-page 3 \
  --saveas-object "skill-test/doc/{Page}.png"
```

Parse a direct HTML preview link without credentials:

```bash
python3 scripts/doc_preview_html_url.py \
  --direct-url "https://your-bucket.tos-cn-beijing.volces.com/doc.docx?x-tos-process=doc-preview&x-tos-doc-dst-type=html"
```

## Document Roles

- `SKILL.md`: trigger-oriented instructions for agents deciding whether to load this skill
- `README.md`: setup guide and runnable entry points for humans and agents
- `REFERENCE.md`: parameter mapping and response semantics
- `WORKFLOWS.md`: end-to-end examples and usage patterns
- `scripts/`: executable examples for common document-processing tasks

## Usage Notes

- For `doc-preview`, pass all document-processing options in the signed URL query string.
- `doc_preview_params.py` is the preferred way to build query parameters consistently.
- The helper now automatically URL-safe-Base64 encodes query-based `x-tos-save-bucket` and `x-tos-save-object`, which is required for the batch screenshot path to succeed.
- `doc_batch_screenshot.py` currently enforces the backend contract for PDF-only batch image export and requires `{Page}` in the destination object key.
- HTML preview flows may require extracting and decoding a token from the returned HTML.
- For buckets created after Jan 03, 2024, online preview may require a custom domain rather than the default TOS domain.
- Official Volcengine TOS documentation remains the source of truth for the full parameter matrix.

## Related Files

- Parameter reference: [REFERENCE.md](REFERENCE.md)
- Workflow guide: [WORKFLOWS.md](WORKFLOWS.md)

## License

This skill is licensed under the Apache License 2.0. See [LICENSE](LICENSE).
