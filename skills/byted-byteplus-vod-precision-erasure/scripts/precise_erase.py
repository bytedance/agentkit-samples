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
precise_erase.py — BytePlus VOD precision erasure (StartExecution Task Type Erase)

Submits OperationTaskErase jobs and polls GetExecution until completion.

Usage:
  uv run python scripts/precise_erase.py '<json_args>'
  uv run python scripts/precise_erase.py @params.json

See references/precise_erase.md (skill: byted-byteplus-vod-precision-erasure).
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vod_client import get_client, get_space_name, build_media_input, get_play_url_by_filename, out, log, bail

# ── Polling configuration ──────────────────────────────────────────────────
POLL_INTERVAL = float(os.environ.get("VOD_POLL_INTERVAL", "5"))
POLL_MAX = int(os.environ.get("VOD_POLL_MAX", "360"))  # 360 × 5s = 30 minutes

# ── VOD API constants ──────────────────────────────────────────────────────
_ACTION_START = "StartExecution"
_ACTION_GET = "GetExecution"
_VERSION_EXEC = "2025-07-01"

_PENDING = {"", "PendingStart", "Running"}
_TERMINAL_FAIL = {"Failed", "Terminated"}

_CLIP_MODE_API = {
    "skip": "Skip",
    "selected": "Selected",
}


def _truthy(v) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    return False


def _parse_clip_filter(args: dict) -> dict | None:
    if "clip_filter" not in args:
        return None
    cf = args.get("clip_filter")
    if cf is None:
        return None
    if not isinstance(cf, dict):
        bail("precise_erase: 'clip_filter' must be an object or null")
    mode_raw = cf.get("mode")
    if mode_raw is None or (isinstance(mode_raw, str) and not mode_raw.strip()):
        bail("precise_erase: when 'clip_filter' is set, 'clip_filter.mode' is required (skip or selected)")
    mode_key = str(mode_raw).strip().lower()
    if mode_key not in _CLIP_MODE_API:
        bail("precise_erase: 'clip_filter.mode' must be 'skip' or 'selected'")
    clips_raw = cf.get("clips")
    if clips_raw is None:
        bail("precise_erase: when using clip_filter, 'clip_filter.clips' is required (non-empty array)")
    if not isinstance(clips_raw, list) or len(clips_raw) < 1:
        bail("precise_erase: 'clip_filter.clips' must be a non-empty array")

    clips_out: list[dict] = []
    for idx, c in enumerate(clips_raw):
        if not isinstance(c, dict):
            bail(f"precise_erase: clip_filter.clips[{idx}] must be an object")
        start = c.get("start", c.get("Start"))
        end = c.get("end", c.get("End"))
        try:
            start_f = float(start)
            end_f = float(end)
        except (TypeError, ValueError):
            bail(f"precise_erase: clip_filter.clips[{idx}] needs numeric 'start' and 'end' (seconds)")
        if end_f <= start_f:
            bail(f"precise_erase: clip_filter.clips[{idx}]: end must be greater than start")
        clips_out.append({"Start": start_f, "End": end_f})

    return {
        "Mode": _CLIP_MODE_API[mode_key],
        "Clips": clips_out,
    }


def _parse_include_erase_detail(args: dict) -> bool:
    """Maps to API WithEraseInfo (default true)."""
    if "with_erase_info" not in args:
        return True
    return _truthy(args.get("with_erase_info"))


def _parse_erase_type_subtitle_vs_text(args: dict) -> tuple[str, dict]:
    """
    Default subtitle-only OCR; optional broader 'text' type.
    Returns (Auto.Type api value, auto_extra dict merged into Auto).
    """
    if _truthy(args.get("text")):
        type_api = "Text"
        extra: dict = {}
    elif _truthy(args.get("all_text")):
        type_api = "Text"
        extra = {}
    else:
        type_api = "Subtitle"
        extra = {"SubtitleFilter": {}}
    return type_api, extra


def build_erase_operation(args: dict) -> dict:
    """Construct OperationTaskErase payload (always Auto; NewVid always true)."""
    include_detail = _parse_include_erase_detail(args)
    clip_filter = _parse_clip_filter(args)
    type_api, extra = _parse_erase_type_subtitle_vs_text(args)

    auto_block: dict = {"Type": type_api, **extra}

    erase: dict = {
        "Mode": "Auto",
        "Auto": auto_block,
        "WithEraseInfo": include_detail,
        "NewVid": True,
    }
    if clip_filter is not None:
        erase["EraseOption"] = {"ClipFilter": clip_filter}

    return erase


def _start_execution(client, payload: dict) -> str:
    resp = client.post(_ACTION_START, _VERSION_EXEC, payload)
    result = resp.get("Result", {}) or {}
    run_id = result.get("RunId", "")
    if not run_id:
        bail(f"StartExecution did not return a RunId, response: {resp}")
    return run_id


def _get_execution(client, run_id: str, *, include_erase_detail: bool) -> dict:
    resp = client.get(_ACTION_GET, _VERSION_EXEC, {"RunId": run_id})
    result = resp.get("Result", {}) or {}
    status = result.get("Status", "")
    space_name = (result.get("Meta", {}) or {}).get("SpaceName", "")

    if status != "Success":
        return {
            "Status": status,
            "Code": result.get("Code", ""),
            "SpaceName": space_name,
        }

    output = ((result.get("Output", {}) or {}).get("Task", {}) or {})
    erase = output.get("Erase", {}) or {}
    file_info = erase.get("File", {}) or {}
    vid = (file_info.get("Vid") or "").strip()
    file_name = (file_info.get("FileName") or "").strip()
    file_id = (file_info.get("FileId") or file_info.get("StoreId") or vid or "").strip()

    direct_url = file_name
    url = ""
    if direct_url and space_name:
        url = get_play_url_by_filename(
            client,
            space_name,
            direct_url,
            expired_minutes=int(os.environ.get("VOD_URL_EXPIRE_MINUTES", "60")),
        )

    source = ""
    if vid:
        source = f"vid://{vid}"
    elif direct_url:
        source = f"directurl://{direct_url}"

    out_obj: dict = {
        "Status": "Success",
        "SpaceName": space_name,
        "VideoUrls": [
            {
                "FileId": file_id,
                "Vid": vid,
                "DirectUrl": direct_url,
                "Source": source,
                "Url": url,
            }
        ],
        "AudioUrls": [],
        "Texts": [],
    }
    if include_erase_detail:
        out_obj["EraseMeta"] = {
            "Duration": erase.get("Duration"),
            "Info": erase.get("Info"),
        }
    else:
        out_obj["EraseMeta"] = {}

    return out_obj


def poll_erase(
    client,
    run_id: str,
    space_name: str,
    *,
    include_erase_detail: bool = True,
) -> dict:
    for i in range(1, POLL_MAX + 1):
        log(f"Polling precise_erase job [{i}/{POLL_MAX}] RunId={run_id} ...")
        try:
            result = _get_execution(client, run_id, include_erase_detail=include_erase_detail)
        except Exception as exc:
            log(f"  query exception: {exc}")
            time.sleep(POLL_INTERVAL)
            continue

        status = result.get("Status", "")

        if status in _PENDING:
            log(f"  status={status!r}, waiting {POLL_INTERVAL}s ...")
            time.sleep(POLL_INTERVAL)
            continue

        if status in _TERMINAL_FAIL:
            ret = {
                "Status": status,
                "Code": result.get("Code", ""),
                "SpaceName": result.get("SpaceName", space_name),
            }
            if status == "Failed":
                ret["resume_hint"] = {
                    "description": "The job failed; check arguments and resubmit, or resume polling with the command below",
                    "command": f"uv run python scripts/poll_execution.py '{run_id}' {space_name}",
                }
            else:
                ret["note"] = "The job was terminated; please resubmit."
            return ret

        if status == "Success":
            return result

        log(f"  unknown status={status!r}, continuing to wait ...")
        time.sleep(POLL_INTERVAL)

    return {
        "error": f"Polling timed out ({POLL_MAX} attempts × {POLL_INTERVAL}s); the job is still processing",
        "resume_hint": {
            "description": "The job has not finished yet; resume polling with the command below",
            "command": f"uv run python scripts/poll_execution.py '{run_id}' {space_name}",
        },
    }


def main():
    if len(sys.argv) < 2:
        bail("Usage: uv run python scripts/precise_erase.py '<json_args>'")

    raw = sys.argv[1]
    if raw.startswith("@"):
        fpath = raw[1:]
        if not Path(fpath).is_file():
            bail(f"Parameter file does not exist: {fpath}")
        with open(fpath, "r", encoding="utf-8") as f:
            raw = f.read()

    try:
        args = json.loads(raw)
    except json.JSONDecodeError as e:
        bail(f"Failed to parse JSON arguments: {e}")

    asset_type = args.get("type", "Vid")
    video = args.get("video", "")
    if not video:
        bail("precise_erase: the 'video' field must not be empty")

    space_name = get_space_name(argv_pos=2)
    client = get_client()

    media_input = build_media_input(asset_type, video, space_name)
    erase_body = build_erase_operation(args)

    payload = {
        "Input": media_input,
        "Operation": {
            "Type": "Task",
            "Task": {
                "Type": "Erase",
                "Erase": erase_body,
            },
        },
    }

    flags: list[str] = []
    auto = erase_body.get("Auto") or {}
    flags.append("text" if auto.get("Type") == "Text" else "subtitle")
    if erase_body.get("EraseOption"):
        flags.append("clip_filter")
    if not erase_body.get("WithEraseInfo", True):
        flags.append("no_erase_detail")
    log(
        "Submitting precise_erase job, "
        f"video={video} type={asset_type} opts={'+'.join(flags)}"
    )
    try:
        run_id = _start_execution(client, payload)
    except SystemExit:
        raise
    except Exception as exc:
        bail(f"Failed to submit precise_erase job: {exc}")

    log(f"Job submitted, RunId={run_id}, starting polling ...")
    out(
        poll_erase(
            client,
            run_id,
            space_name,
            include_erase_detail=bool(erase_body.get("WithEraseInfo", True)),
        )
    )


if __name__ == "__main__":
    main()
