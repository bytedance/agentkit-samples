---
name: byted-tos-file-process
description: "Compresses and uncompresses file objects stored in Volcengine TOS through TOS data-process async jobs. Use this skill when the user needs to zip files, unzip archives, create tar or zstd archives, extract compressed files, pack multiple TOS objects into a single archive, bundle files together, or distribute files as a package — even if they don't explicitly mention 'compression', 'archive', '打包', or '压缩'."
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

# Volcengine TOS File Process

Compress and uncompress file objects stored in Volcengine TOS through the TOS gateway's `file_jobs` API.

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

## Environment Variables

This skill relies on the TOS identity declared in the `metadata` block. Common runtime variables are:

| Environment Variable | Required | Description |
| --- | --- | --- |
| `TOS_ACCESS_KEY` | Yes | TOS access key ID |
| `TOS_SECRET_KEY` | Yes | TOS secret access key |
| `TOS_ENDPOINT` | Yes | TOS endpoint URL |
| `TOS_REGION` | Yes | TOS region |
| `TOS_BUCKET` | Yes | Source bucket that stores the file objects |
| `TOS_OBJECT_KEY` | No | Source object key. Can be overridden with `--key` or `--keys` |
| `TOS_SECURITY_TOKEN` | No | STS session token when using temporary credentials |

## Quick start

```bash
# Compress multiple TOS objects into a zip archive and wait for completion
python3 {baseDir}/scripts/file_compress.py \
  --keys file1.jpg,file2.txt \
  --format zip \
  --output-key output/archive.zip \
  --wait

# Uncompress a zip archive and wait for completion
python3 {baseDir}/scripts/file_uncompress.py \
  --key output/archive.zip \
  --prefix output/unzipped/ \
  --wait
```

## Available scripts

| Script | Purpose |
|--------|---------|
| `scripts/file_compress.py` | Submit an async `FileCompress` job via the TOS gateway's `file_jobs` API that compresses TOS objects into an archive (zip/tar/zst). Supports `--wait` to poll until completion. |
| `scripts/file_uncompress.py` | Submit an async `FileUncompress` job via the TOS gateway's `file_jobs` API that extracts an archive in TOS. Supports `--wait` to poll until completion. |
| `scripts/tos_jobs_client.py` | Shared client for TOS gateway `file_jobs` APIs using pre-signed URL auth. |

## Rules

- **TOS gateway API**: This skill uses the TOS gateway's `file_jobs` API with `job_type=FileCompress` or `job_type=FileUncompress`. Authentication is handled via `pre_signed_url` from the TOS Python SDK and the TOS identity declared in the `metadata` block above.
- **Supported archive formats**: Compress supports `zip`, `tar`, and `zst`. The output object key suffix must match the chosen format (`.zip`, `.tar`, `.zst`).
- **Async job model**: The scripts create async jobs and optionally wait for completion with the `--wait` flag.
- **Language**: Reply in the user's preferred language.

## Further reading

- Setup and environment: [README.md](README.md)
- Parameter reference: [REFERENCE.md](REFERENCE.md)
- End-to-end workflows: [WORKFLOWS.md](WORKFLOWS.md)
