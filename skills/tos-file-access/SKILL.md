---
name: tos-file-access
description: Upload files or directories to Volcano Engine TOS (Torch Object Storage) and download files from URLs. Use this skill when (1) Upload Agent-generated files or directories (like videos, images, reports, output folders) to TOS for sharing, (2) Download files from URLs before Agent processing.
license: Complete terms in LICENSE.txt
---

# TOS File Access

This skill provides utilities for uploading files and directories to Volcano Engine TOS (Torch Object Storage) and downloading files from URLs.

## Overview

**TOS (Torch Object Storage)** is Volcano Engine's object storage service, similar to AWS S3. This skill enables:

- **Upload**: Upload Agent-generated files or entire directories to TOS and get shareable signed URLs (for files) or TOS paths (for directories)
- **Download**: Download files from URLs to local storage for Agent processing

## Typical Workflows

### Pre-Agent Execution: Download User Files

When users provide file URLs (TOS or external), download them before processing:

```bash
# Download single file
python scripts/file_download.py https://example.com/data.csv

# Download multiple files
python scripts/file_download.py https://example.com/data.csv https://example.com/config.json

# Specify save directory and filenames
python scripts/file_download.py https://example.com/data.csv --save-dir /workspace --filenames dataset.csv
```

### Post-Agent Execution: Upload Output Files or Directories

After generating files or directories (videos, charts, reports, output folders, etc.), upload them to TOS for user access:

```bash
# Upload single file (auto-detected)
python scripts/tos_upload.py /path/to/output.mp4 --bucket my-bucket

# Upload entire directory (auto-detected)
python scripts/tos_upload.py /path/to/output_folder --bucket my-bucket

# Upload with custom region and expiration
python scripts/tos_upload.py /path/to/report.pdf --bucket my-bucket --region cn-beijing --expires 86400
```

## Scripts

### `scripts/file_download.py`

Download files from URLs to local storage.

**Usage:**

```bash
python scripts/file_download.py <url1> [url2 ...] [--save-dir DIR] [--filenames NAME1 NAME2 ...]
```

**Arguments:**

- `urls`: One or more URLs to download (positional, required)
- `--save-dir`: Save directory (optional, defaults to `/tmp`)
- `--filenames`: Custom filenames for downloaded files (optional, must match number of URLs)

**Examples:**

```bash
# Download single file to /tmp
python scripts/file_download.py https://tos-cn-beijing.volces.com/bucket/file.pdf

# Download to specific directory
python scripts/file_download.py https://example.com/data.json --save-dir /workspace/data

# Download multiple files with custom names
python scripts/file_download.py \
  https://example.com/file1.pdf \
  https://example.com/file2.jpg \
  --save-dir /workspace \
  --filenames document.pdf image.jpg
```

**Returns:** Prints absolute paths of downloaded files (one per line)

### `scripts/tos_upload.py`

Upload files or directories to TOS and generate signed access URLs (for files) or TOS paths (for directories).

**Key Features:**

- **Auto-detection**: Automatically detects whether the path is a file or directory
- **Session-based paths**: Uses `TOOL_USER_SESSION_ID` environment variable to organize uploads
- **Preserves structure**: For directories, maintains the full directory structure in TOS
- **Automatic bucket creation**: Creates bucket if it doesn't exist (with private ACL)

**Usage:**

```bash
python scripts/tos_upload.py <path> --bucket BUCKET [--region REGION] [--expires SECONDS]
```

**Arguments:**

- `path`: Local file or directory path to upload (positional, required)
- `--bucket`: TOS bucket name (required)
- `--region`: TOS region (optional, defaults to `cn-beijing`)
- `--expires`: Signed URL expiration in seconds (optional, defaults to 604800 = 7 days, only applies to file uploads)

**Upload Structure:**

- **File**: `upload/{session_prefix}/{filename}`
  - Example: `upload/skill_agent_veadk_default_user_tmp-session-20251210150057/video.mp4`
- **Directory**: `upload/{session_prefix}/{directory_name}/{relative_path}`
  - Example: `upload/skill_agent_veadk_default_user_tmp-session-20251210150057/output_folder/file1.txt`

**Session Prefix:**

- If `TOOL_USER_SESSION_ID` is set, uses that value as prefix
- Otherwise, falls back to timestamp format `YYYYMMDD_HHMMSS`

**Authentication:**
Requires one of:

- Environment variables: `VOLCENGINE_ACCESS_KEY` and `VOLCENGINE_SECRET_KEY`
- VeFaaS IAM Role (automatic credential retrieval)

**Examples:**

```bash
# Upload single file (auto-detected)
python scripts/tos_upload.py /workspace/output.mp4 --bucket my-bucket

# Upload entire directory (auto-detected)
python scripts/tos_upload.py /workspace/results_folder --bucket my-bucket

# Upload to different region with 1-day expiration
python scripts/tos_upload.py /workspace/report.pdf \
  --bucket my-reports \
  --region cn-beijing \
  --expires 86400

# Upload directory with all options
python scripts/tos_upload.py /workspace/output_dir \
  --bucket data-storage \
  --region cn-beijing
```

**Returns:**

- **For files**: Prints a signed URL that can be shared with users (valid for specified duration)
- **For directories**: Prints a TOS path in format `tos://bucket-name/path/to/directory`

**Output Examples:**

```bash
# File upload output
============================================================
✅ Upload Successful!
============================================================
Signed URL:
https://my-bucket.tos-cn-beijing.volces.com/upload/skill_agent_xxx/video.mp4?X-Tos-Signature=...
============================================================

# Directory upload output
============================================================
✅ Upload Successful!
============================================================
TOS Path:
tos://my-bucket/upload/skill_agent_xxx/output_folder
============================================================
```

## Environment Variables

- `VOLCENGINE_ACCESS_KEY`: Volcano Engine access key for TOS authentication
- `VOLCENGINE_SECRET_KEY`: Volcano Engine secret key for TOS authentication
- `TOOL_USER_SESSION_ID`: Session ID used to generate organized upload paths (optional, falls back to timestamp)

## Common Use Cases

1. **Video Processing**: Download source video → process → upload result

   ```bash
   # Download
   python scripts/file_download.py https://example.com/input.mp4 --save-dir /workspace
   # Process video (your code here)
   # Upload result
   python scripts/tos_upload.py /workspace/output.mp4 --bucket video-storage
   ```

2. **Data Analysis**: Download datasets → analyze → upload charts/reports folder

   ```bash
   # Download data
   python scripts/file_download.py https://example.com/data.csv --save-dir /workspace
   # Analyze and generate charts (your code here)
   # Upload entire results folder
   python scripts/tos_upload.py /workspace/analysis_results --bucket analysis-bucket
   ```

3. **Batch Processing**: Process multiple files and upload output directory

   ```bash
   # Process files (your code here, generates /workspace/batch_output/)
   # Upload entire output directory
   python scripts/tos_upload.py /workspace/batch_output --bucket batch-results
   ```

4. **Project Export**: Upload a complete project directory structure

   ```bash
   # Upload project directory with subdirectories
   python scripts/tos_upload.py /workspace/my_project --bucket project-storage
   # Result: tos://project-storage/upload/{session_id}/my_project/...
   ```

## Notes

- **Auto-detection**: No need to specify whether uploading a file or directory - the script detects automatically
- **Session organization**: Files and directories are automatically organized by session ID for easy tracking
- **Signed URLs** (files only): Valid for 7 days by default (adjustable via `--expires`)
- **TOS Paths** (directories): Returned as `tos://bucket/path` format for reference
- **Structure preservation**: Directory uploads maintain the complete folder structure in TOS
- **No timestamp in filenames**: Original filenames are preserved (session prefix provides uniqueness)
- **Auto-bucket creation**: Bucket is automatically created with private ACL if it doesn't exist
- **Auto-deduplication**: Downloads automatically rename files if they already exist
- **IAM Role support**: Scripts automatically retrieve credentials from VeFaaS IAM when available
- **Error handling**: Scripts print clear error messages for network, permission, or file issues
- **Bucket requirement**: Bucket name must be specified via `--bucket` parameter (required)
