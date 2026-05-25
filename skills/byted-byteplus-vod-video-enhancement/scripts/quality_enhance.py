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
quality_enhance.py — comprehensive quality restoration

AI-based comprehensive video quality restoration: removes compression artifacts,
noise, and scratches, improving overall clarity and color rendition.

Usage:
  uv run python scripts/quality_enhance.py '<json_args>'
  uv run python scripts/quality_enhance.py @params.json

See references/quality-enhance.md for the json_args fields.
"""

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
_VALID_MOE_CONFIGS = {"common", "ugc", "short_series", "aigc", "old_film"}
_VALID_REPAIR_STYLES = {1, 2}
_VALID_TARGET_RES = frozenset(
    {"240p", "360p", "480p", "540p", "720p", "1080p", "2k", "4k"}
)
# User-facing aliases that mean "keep source resolution" (omit MoeEnhance.Target)
_RES_ORIGINAL_ALIASES = frozenset(
    {"", "original", "source", "same", "native", "none", "default"}
)


def _start_execution(client, payload: dict) -> str:
    """Submit StartExecution and return the RunId."""
    resp = client.post(_ACTION_START, _VERSION_EXEC, payload)
    result = resp.get("Result", {}) or {}
    run_id = result.get("RunId", "")
    if not run_id:
        bail(f"StartExecution did not return a RunId, response: {resp}")
    return run_id


def _get_execution(client, run_id: str) -> dict:
    """Call GetExecution and return a structured result."""
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

    # Parse the enhanceVideo output
    output = ((result.get("Output", {}) or {}).get("Task", {}) or {})
    enhance = output.get("Enhance", {}) or {}
    store_uri = enhance.get("StoreUri", "")
    file_id = enhance.get("FileId", "")

    # Extract the FileName from StoreUri (strip the tos://<bucket>/ prefix)
    direct_url = ""
    if store_uri:
        from urllib.parse import urlparse
        parsed = urlparse(store_uri)
        parts = parsed.path.split("/")[1:]
        direct_url = "/".join(parts)

    url = ""
    if direct_url and space_name:
        url = get_play_url_by_filename(client, space_name, direct_url, expired_minutes=int(os.environ.get("VOD_URL_EXPIRE_MINUTES", "60")))

    return {
        "Status": "Success",
        "SpaceName": space_name,
        "VideoUrls": [
            {
                "FileId": file_id,
                "DirectUrl": direct_url,
                "Source": f"directurl://{direct_url}" if direct_url else "",
                "Url": url,
            }
        ],
        "AudioUrls": [],
        "Texts": [],
    }


def poll_enhance(client, run_id: str, space_name: str) -> dict:
    """Poll the enhanceVideo job until a terminal state is reached."""
    for i in range(1, POLL_MAX + 1):
        log(f"Polling quality restoration job [{i}/{POLL_MAX}] RunId={run_id} ...")
        try:
            result = _get_execution(client, run_id)
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
                    "description": "The job failed; check the parameters and resubmit, or resume polling with the command below",
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


def _parse_moe_config(args: dict) -> str:
    if "config" not in args:
        bail("quality_enhance: 'config' is required (recommended default: common)")
    config = str(args.get("config", "")).strip()
    if config not in _VALID_MOE_CONFIGS:
        bail(
            "quality_enhance: 'config' must be one of "
            + ", ".join(sorted(_VALID_MOE_CONFIGS))
        )
    return config


def _parse_repair_style(args: dict) -> int:
    if "repair_style" not in args:
        bail("quality_enhance: 'repair_style' is required (recommended default: 1 / Standard)")
    raw = args.get("repair_style")
    try:
        repair_style = int(raw)
    except (TypeError, ValueError):
        bail("quality_enhance: 'repair_style' must be 1 (standard) or 2 (pro)")
    if repair_style not in _VALID_REPAIR_STYLES:
        bail("quality_enhance: 'repair_style' must be 1 (standard) or 2 (pro)")
    return repair_style


def _normalize_target_res(raw: str) -> str:
    """Normalize VolcMoeTarget.Res (e.g. 1080P -> 1080p, 2K -> 2k)."""
    s = raw.strip()
    lower = s.lower()
    if lower in _VALID_TARGET_RES:
        return lower
    if lower.endswith("p") and lower[:-1].isdigit():
        candidate = lower
        if candidate in _VALID_TARGET_RES:
            return candidate
    return s


def _parse_target_res(args: dict) -> str | None:
    """
    Optional MoeEnhance.Target.Res. None => omit Target (API keeps source resolution).
    Accepts json field `res` (maps to Target.Res).
    """
    if "res" not in args:
        return None
    raw = args.get("res")
    if raw is None:
        return None
    if not isinstance(raw, str):
        bail("quality_enhance: 'res' must be a string when provided")
    key = raw.strip().lower()
    if key in _RES_ORIGINAL_ALIASES:
        return None
    normalized = _normalize_target_res(raw)
    if normalized not in _VALID_TARGET_RES:
        bail(
            "quality_enhance: 'res' must be one of "
            + ", ".join(sorted(_VALID_TARGET_RES))
            + " (or omit / use empty string for source resolution)"
        )
    return normalized


def _build_moe_enhance(config: str, repair_style: int, target_res: str | None) -> dict:
    moe: dict = {
        "Config": config,
        "VideoStrategy": {"RepairStyle": repair_style, "RepairStrength": 0},
    }
    if target_res is not None:
        moe["Target"] = {"Res": target_res}
    return moe


def main():
    if len(sys.argv) < 2:
        bail("Usage: uv run python scripts/quality_enhance.py '<json_args>'")

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
        bail("quality_enhance: the 'video' field must not be empty")

    space_name = get_space_name(argv_pos=2)
    client = get_client()

    media_input = build_media_input(asset_type, video, space_name)
    config = _parse_moe_config(args)
    repair_style = _parse_repair_style(args)
    target_res = _parse_target_res(args)
    moe_enhance = _build_moe_enhance(config, repair_style, target_res)

    payload = {
        "Input": media_input,
        "Operation": {
            "Type": "Task",
            "Task": {
                "Type": "Enhance",
                "Enhance": {
                    "Type": "Moe",
                    "MoeEnhance": moe_enhance,
                },
            },
        },
    }

    res_note = target_res or "source"
    log(
        f"Submitting quality restoration job, video={video} type={asset_type} "
        f"config={config} repair_style={repair_style} res={res_note}"
    )
    try:
        run_id = _start_execution(client, payload)
    except SystemExit:
        raise
    except Exception as exc:
        bail(f"Failed to submit quality restoration job: {exc}")

    log(f"Job submitted, RunId={run_id}, starting polling ...")
    out(poll_enhance(client, run_id, space_name))


if __name__ == "__main__":
    main()
