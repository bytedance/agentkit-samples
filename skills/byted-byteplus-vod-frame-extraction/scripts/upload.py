#!/usr/bin/env python3
# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
upload.py — upload a media asset to BytePlus VOD and return the Vid

Supported inputs:
  1) Local file path  → ApplyUploadInfo + TOS direct/chunked PUT + CommitUploadInfo
  2) http/https link  → UploadMediaByUrl (async) + poll QueryUploadTaskInfo

Usage:
  uv run python scripts/upload.py "<local_path_or_url>" [space_name]

Output (JSON on stdout):
  {"Vid":"vxxxx","Source":"vid://vxxxx","PlayURL":"...","PosterUri":"","FileName":"...","SpaceName":"...","SourceUrl":"..."}

  PlayURL is built via get_play_url_by_filename (storage host / play domain + path).
"""

import os
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vod_client import (
    get_client,
    get_space_name,
    get_play_url_by_filename,
    apply_upload_info,
    commit_upload_info,
    out,
    log,
    bail,
)
from tos_upload import upload_to_tos

# ── Polling configuration ──────────────────────────────────────────────────
POLL_INTERVAL = float(os.environ.get("VOD_POLL_INTERVAL", "5"))
POLL_MAX = int(os.environ.get("VOD_POLL_MAX", "360"))  # 360 × 5s = 30 minutes

# ── VOD API constants ──────────────────────────────────────────────────────
_ACTION_UPLOAD_BY_URL = "UploadMediaByUrl"
_ACTION_QUERY_TASK = "QueryUploadTaskInfo"
_VERSION = "2023-01-01"


# ══════════════════════════════════════════════════════════════════════════
# Path safety: restrict which local paths may be uploaded
# ══════════════════════════════════════════════════════════════════════════

_ALLOWED_PREFIXES: list[str] | None = None


def _get_allowed_prefixes() -> list[str]:
    global _ALLOWED_PREFIXES
    if _ALLOWED_PREFIXES is not None:
        return _ALLOWED_PREFIXES

    prefixes: list[str] = []

    # 1) WORKSPACE (or cwd) — the project the agent is operating in
    ws = os.environ.get("WORKSPACE", os.getcwd())
    prefixes.append(os.path.realpath(ws))

    # 2) sibling userdata/ directory (Cursor sandbox convention)
    ud = os.path.join(os.path.dirname(ws), "userdata") if ws else ""
    if ud:
        prefixes.append(os.path.realpath(ud))

    # 3) /tmp — commonly used for scratch files
    prefixes.append("/tmp")

    # 4) VOD_UPLOAD_ALLOWED_DIRS — comma-separated extra directories
    extra = os.environ.get("VOD_UPLOAD_ALLOWED_DIRS", "")
    for d in extra.split(","):
        d = d.strip()
        if d:
            prefixes.append(os.path.realpath(d))

    _ALLOWED_PREFIXES = prefixes
    return _ALLOWED_PREFIXES


def _validate_local_path(file_path: str) -> None:
    """Ensure the resolved path falls under an allowed prefix (symlink-safe)."""
    real = os.path.realpath(file_path)
    for prefix in _get_allowed_prefixes():
        if real == prefix or real.startswith(prefix + os.sep):
            return
    bail(
        f"Path not allowed. Only files under workspace/, userdata/, /tmp, "
        f"or VOD_UPLOAD_ALLOWED_DIRS may be uploaded. Rejected: {file_path}"
    )


def _guess_ext(path_str: str) -> str:
    _, ext = os.path.splitext(path_str or "")
    ext = ext.strip()
    if not ext:
        bail("The file must carry a file extension (e.g. .mp4 / .mov / .mp3)")
    if not ext.startswith("."):
        ext = "." + ext
    return ext


def _is_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://")


# ══════════════════════════════════════════════════════════════════════════
# URL upload (async pull)
# ══════════════════════════════════════════════════════════════════════════

def _submit_url_upload(client, space_name: str, source_url: str, file_ext: str) -> list:
    file_name = f"{uuid.uuid4().hex}{file_ext}"
    body = {
        "SpaceName": space_name,
        "URLSets": [
            {
                "SourceUrl": source_url,
                "FileExtension": file_ext,
                "FileName": file_name,
            }
        ],
    }
    log(f"Submitting URL upload: {source_url}")
    resp = client.post(_ACTION_UPLOAD_BY_URL, _VERSION, body)
    result = resp.get("Result", {}) or {}
    data = result.get("Data", []) or []
    job_ids = [item["JobId"] for item in data if isinstance(item, dict) and item.get("JobId")]
    if not job_ids:
        bail(f"UploadMediaByUrl did not return a JobId, response: {resp}")
    return job_ids


def _poll_upload_task(client, job_ids_str: str) -> dict:
    last_state = ""
    for i in range(1, POLL_MAX + 1):
        log(f"Polling upload task [{i}/{POLL_MAX}] JobIds={job_ids_str}")
        try:
            resp = client.get(_ACTION_QUERY_TASK, _VERSION, {"JobIds": job_ids_str})
        except Exception as exc:
            log(f"  query exception: {exc}")
            time.sleep(POLL_INTERVAL)
            continue

        result = resp.get("Result", {}) or {}
        data = result.get("Data", {}) or {}
        media_list = data.get("MediaInfoList", []) or []

        if not media_list:
            time.sleep(POLL_INTERVAL)
            continue

        item = media_list[0]
        state = item.get("State", "")
        last_state = state or last_state
        vid = item.get("Vid", "")

        if vid:
            source_info = item.get("SourceInfo", {}) or {}
            return {
                "Vid": vid,
                "FileName": source_info.get("FileName", ""),
                "State": state,
                "SpaceName": item.get("SpaceName", ""),
                "JobId": item.get("JobId", ""),
            }

        if state.lower() in {"fail", "failed", "error"}:
            bail(f"URL pull upload failed: State={state!r}, JobIds={job_ids_str}")

        time.sleep(POLL_INTERVAL)

    return {
        "error": f"Polling timed out ({POLL_MAX} attempts × {POLL_INTERVAL}s); the URL pull upload is still processing",
        "resume_hint": {
            "description": "The URL upload has not finished yet; retry with the command below",
            "command": 'uv run python scripts/upload.py "<original URL>" [space_name]',
        },
        "JobIds": job_ids_str,
        "State": last_state,
    }


def _do_url_upload(client, space_name: str, source_url: str) -> None:
    file_ext = _guess_ext(urlparse(source_url).path)
    try:
        job_ids = _submit_url_upload(client, space_name, source_url, file_ext)
    except SystemExit:
        raise
    except Exception as exc:
        bail(f"Failed to submit URL upload: {exc}")

    job_ids_str = ",".join(job_ids)
    log(f"Upload job submitted, JobIds={job_ids_str}")

    info = _poll_upload_task(client, job_ids_str)
    if "error" in info:
        out(info)
        return

    vid = info.get("Vid", "")
    file_name = (info.get("FileName") or "").strip()
    play_url = _build_play_url(client, space_name, file_name, vid)
    out({
        "Vid": vid,
        "Source": f"vid://{vid}",
        "PlayURL": play_url,
        "PosterUri": "",
        "FileName": file_name,
        "SpaceName": space_name,
        "SourceUrl": source_url,
        "JobId": job_ids_str,
    })


# ══════════════════════════════════════════════════════════════════════════
# Local file upload (ApplyUploadInfo → TOS → CommitUploadInfo)
# ══════════════════════════════════════════════════════════════════════════

def _do_local_upload(client, space_name: str, file_path: str) -> None:
    _validate_local_path(file_path)
    if not os.path.isfile(file_path):
        bail(f"Local file not found: {file_path}")

    file_ext = _guess_ext(file_path)
    file_size = os.path.getsize(file_path)
    file_name = f"{uuid.uuid4().hex}{file_ext}"
    log(f"Local upload: {file_path} ({file_size} bytes) → FileName={file_name}")

    # Step 1: ApplyUploadInfo
    try:
        apply_data = apply_upload_info(
            client, space_name,
            file_size=file_size, file_name=file_name, file_ext=file_ext,
        )
    except SystemExit:
        raise
    except Exception as exc:
        bail(f"ApplyUploadInfo failed: {exc}")

    # Step 2: upload binary to TOS
    try:
        session_key = upload_to_tos(apply_data, file_path, log_fn=log)
    except SystemExit:
        raise
    except Exception as exc:
        bail(f"TOS upload failed: {exc}")

    # Step 3: CommitUploadInfo
    try:
        commit_data = commit_upload_info(client, space_name, session_key)
    except SystemExit:
        raise
    except Exception as exc:
        bail(f"CommitUploadInfo failed: {exc}")

    vid = commit_data.get("Vid", "")
    if not vid:
        bail("CommitUploadInfo succeeded but returned no Vid")
    source_info = commit_data.get("SourceInfo") or {}
    returned_file_name = source_info.get("FileName", "")

    play_url = _build_play_url(client, space_name, returned_file_name, vid)
    out({
        "Vid": vid,
        "Source": f"vid://{vid}",
        "PlayURL": play_url,
        "PosterUri": commit_data.get("PosterUri", ""),
        "FileName": returned_file_name,
        "SpaceName": space_name,
        "SourceUrl": file_path,
    })


# ══════════════════════════════════════════════════════════════════════════
# Shared: build a play URL from FileName (fallback to Vid as path key)
# ══════════════════════════════════════════════════════════════════════════

def _build_play_url(client, space_name: str, file_name: str, vid: str) -> str:
    vid_key = vid[len("vid://"):] if vid.startswith("vid://") else vid
    path_for_url = (file_name or vid_key).strip()
    if not path_for_url:
        return ""
    expired = int(os.environ.get("VOD_URL_EXPIRE_MINUTES", "60"))
    if not file_name and vid_key:
        log("No FileName; trying get_play_url_by_filename with Vid as path key")
    return get_play_url_by_filename(client, space_name, path_for_url, expired_minutes=expired)


# ══════════════════════════════════════════════════════════════════════════
# main
# ══════════════════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        bail('Usage: uv run python scripts/upload.py "<local_path_or_url>" [space_name]')

    source = sys.argv[1].strip()
    space_name = get_space_name(argv_pos=2)
    client = get_client()

    if _is_url(source):
        _do_url_upload(client, space_name, source)
    else:
        _do_local_upload(client, space_name, source)


if __name__ == "__main__":
    main()
