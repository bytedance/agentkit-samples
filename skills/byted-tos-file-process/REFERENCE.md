# Bytedance TOS File Process Reference

This document explains the async file compression and uncompression paths implemented by this skill.

## Authentication

Authentication is handled by the TOS Python SDK. The `tos_jobs_client.py` shared client signs requests with the TOS identity declared in `SKILL.md` metadata. No additional DP-specific configuration is needed.

## Core Operations

### `FileCompress`

The script `scripts/file_compress.py` compresses TOS objects by:

1. Building a `FileCompressConfig` payload
2. Posting a JSON payload to the TOS gateway's `file_jobs` API with query `file_jobs=&job_type=FileCompress`
3. Polling the job state via the `file_jobs` API with `job_type=FileCompress&job_id=<job_id>`
4. The output is an archive file saved to TOS

### `FileUncompress`

The script `scripts/file_uncompress.py` extracts an archive in TOS by:

1. Building a `FileUncompressConfig` payload
2. Posting a JSON payload to the TOS gateway's `file_jobs` API with query `file_jobs=&job_type=FileUncompress`
3. Polling the job state via the `file_jobs` API with `job_type=FileUncompress&job_id=<job_id>`
4. The extracted files are saved to TOS

## Job Payloads

### FileCompress

The submission body follows the TOS gateway's `file_jobs` API contract:

```json
{
  "Input": {
    "Prefix": "",
    "KeyConfig": [
      {"Key": "file1.jpg"},
      {"Key": "file2.txt"}
    ]
  },
  "FileCompressConfig": {
    "Format": "zip",
    "Flatten": 0
  },
  "Output": {
    "Region": "cn-beijing",
    "Bucket": "source-bucket",
    "Object": "output/archive.zip"
  }
}
```

### FileUncompress

```json
{
  "Input": {
    "Object": "archive.zip"
  },
  "FileUncompressConfig": {
    "Prefix": "output/dir/",
    "PrefixReplaced": 0
  },
  "Output": {
    "Region": "cn-beijing",
    "Bucket": "source-bucket"
  }
}
```

## CLI Mapping

### file_compress.py

| CLI argument | Meaning | Notes |
| --- | --- | --- |
| `--keys` | Comma-separated source object keys | Required |
| `--bucket` | Source TOS bucket | Defaults to `TOS_BUCKET` env |
| `--prefix` | Input prefix filter | Optional, default empty |
| `--format` | Archive format | `zip`, `tar`, or `zst`; default `zip` |
| `--flatten` | Flatten directory structure | `0`=keep structure, `1`=flatten; default `0` |
| `--output-bucket` | Output bucket | Defaults to source bucket |
| `--output-key` | Output archive object key | Default `archive.<ext>` |
| `--wait` | Poll until completion | Optional |
| `--timeout` | Max wait time in seconds | Default `300` |
| `--poll-interval` | Poll interval in seconds | Default `5` |

### file_uncompress.py

| CLI argument | Meaning | Notes |
| --- | --- | --- |
| `--key` | Source archive object key | Required |
| `--bucket` | Source TOS bucket | Defaults to `TOS_BUCKET` env |
| `--output-bucket` | Output bucket | Defaults to source bucket |
| `--prefix` | Target prefix for extracted files | Optional, default empty |
| `--prefix-replaced` | Replace original directory with prefix | `0`=keep original, `1`=replace; default `0` |
| `--wait` | Poll until completion | Optional |
| `--timeout` | Max wait time in seconds | Default `300` |
| `--poll-interval` | Poll interval in seconds | Default `5` |

## Workflow States

The polling client currently treats these states as:

| State | Meaning |
| --- | --- |
| `Submitted` | Job accepted by workflow service |
| `Running` | Backend is processing |
| `Success` | Output should be ready |
| `Failed` | Job finished with error |

## Notes

- The scripts print the raw create-job response when `--wait` is not used.
- When `--wait` is used, the final printed object is the first job item returned by `get_job`.
- Authentication uses the TOS identity declared in `SKILL.md` metadata. No DP-specific configuration is needed.
- For `FileCompress`, the output object key suffix must match the chosen format (`.zip`, `.tar`, `.zst`).
