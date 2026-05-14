# Bytedance TOS File Process Skill

This skill provides an async file-processing toolkit for files stored in Bytedance TOS. It currently focuses on compressing TOS objects into archives and extracting archives back into TOS objects.

## When To Use

Use this skill when you need to:
- Compress multiple TOS objects into a zip, tar, or zst archive
- Uncompress a zip, tar, or zst archive stored in TOS
- Archive files for distribution or storage
- Extract files from an archive in TOS
- Submit an async `FileCompress` or `FileUncompress` job via the TOS gateway's `file_jobs` API and optionally wait for completion

Do not use this skill for:
- Local-only compression workflows that do not involve TOS
- Audio or video transcoding
- Document preview or image transformation

## Why This Skill Exists

The file compression and uncompression paths are exposed as async jobs via the TOS gateway's `file_jobs` API. This skill wraps those APIs into runnable Python scripts so agents can:

1. Submit a `FileCompress` job via the `file_jobs` API to archive TOS objects
2. Submit a `FileUncompress` job via the `file_jobs` API to extract an archive
3. Poll the job state until success or failure

## Directory Layout

```text
byted-tos-file-process/
├── SKILL.md
├── README.md
├── REFERENCE.md
├── WORKFLOWS.md
├── LICENSE
├── requirements.txt
└── scripts/
    ├── file_compress.py
    ├── file_uncompress.py
    └── tos_jobs_client.py
```

## Requirements

- Python 3.7+
- Access to Volcengine TOS
- Valid TOS AK/SK or STS credentials
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
| `TOS_BUCKET` | Yes | Source bucket that stores the file objects. | `my-file-bucket` |
| `TOS_OBJECT_KEY` | No | Source object key. Can be overridden with `--key` or `--keys`. | `files/archive.zip` |
| `TOS_SECURITY_TOKEN` | No | STS session token when using temporary credentials. | `STS...` |

## Quick Start

Export the minimum required configuration:

```bash
export TOS_ACCESS_KEY="YOUR_AK"
export TOS_SECRET_KEY="YOUR_SK"
export TOS_ENDPOINT="https://tos-cn-beijing.volces.com"
export TOS_REGION="cn-beijing"
export TOS_BUCKET="your-file-bucket"
```

Compress multiple objects into a zip archive:

```bash
python3 scripts/file_compress.py \
  --keys file1.jpg,file2.txt \
  --format zip \
  --saveas-object output/archive.zip \
  --wait
```

Uncompress an archive:

```bash
python3 scripts/file_uncompress.py \
  --key output/archive.zip \
  --prefix output/unzipped/ \
  --wait
```

## Usage Notes

- `file_compress.py` accepts `--keys` as a comma-separated list of source object keys.
- `file_uncompress.py` uses `--prefix` and optional `--prefix-replaced`; extraction is prefix-based, so it does not expose `--saveas-object`.
- Async job scripts now support `--job-id` to query an existing job, `--validate` / `--dry-run` to inspect the resolved payload before submission, and `--json` for machine-readable output.
- The output object key suffix must match the chosen format: `.zip` for zip, `.tar` for tar, `.zst` for zst.
- Both scripts use the TOS gateway's `file_jobs` API, authenticated via `pre_signed_url` from the TOS Python SDK. No extra environment variables beyond the standard TOS credentials are needed.
- Successful submission returns a `JobId`; `--wait` then polls the job `State` until `Success` or `Failed`.

## Related Files

- Trigger-oriented usage: [SKILL.md](SKILL.md)
- Parameter reference: [REFERENCE.md](REFERENCE.md)
- Workflow guide: [WORKFLOWS.md](WORKFLOWS.md)

## License

This skill is licensed under the Apache License 2.0. See [LICENSE](LICENSE).
