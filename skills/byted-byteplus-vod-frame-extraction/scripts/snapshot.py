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
snapshot.py — BytePlus VOD frame extraction (StartExecution Task Type Snapshot)

Submits OperationTaskSnapshot jobs and polls GetExecution until completion.

Usage:
  uv run python scripts/snapshot.py '<json_args>' [space_name]
  uv run python scripts/snapshot.py @params.json [space_name]

See references/snapshot.md (skill: byted-byteplus-vod-frame-extraction).
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

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

_STRATEGY_TYPES = {
    "interval": "TimeInterval",
    "time_interval": "TimeInterval",
    "time": "SpecifiedTime",
    "specified_time": "SpecifiedTime",
    "frames": "SpecifiedFrames",
    "specified_frames": "SpecifiedFrames",
    "scene": "SceneChange",
    "scene_change": "SceneChange",
}
_VALID_RESOLUTIONS = {"240p", "360p", "480p", "720p", "1080p"}
_VALID_INDEX_MODES = {"Files", "Index"}


def _truthy(v) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    return False


def _deep_merge(base: dict, extra: dict) -> dict:
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _as_int_list(value, field: str, *, minimum: int = 0, max_len: int | None = None) -> list[int]:
    if not isinstance(value, list) or not value:
        bail(f"snapshot: '{field}' must be a non-empty array")
    if max_len is not None and len(value) > max_len:
        bail(f"snapshot: '{field}' cannot contain more than {max_len} values")
    out_values: list[int] = []
    for idx, raw in enumerate(value):
        try:
            n = int(raw)
        except (TypeError, ValueError):
            bail(f"snapshot: '{field}[{idx}]' must be an integer")
        if n < minimum:
            bail(f"snapshot: '{field}[{idx}]' must be >= {minimum}")
        out_values.append(n)
    return out_values


def _parse_strategy(args: dict) -> dict:
    strategy_obj = args.get("strategy")
    if isinstance(strategy_obj, dict):
        return strategy_obj

    raw_type = strategy_obj or args.get("strategy_type") or args.get("mode") or "specified_time"
    key = str(raw_type).strip().lower()
    strategy_type = _STRATEGY_TYPES.get(key)
    if not strategy_type:
        bail(
            "snapshot: strategy must be one of interval, specified_time, "
            "specified_frames, or scene_change"
        )

    strategy: dict = {"Type": strategy_type}
    if strategy_type == "TimeInterval":
        raw_interval = args.get("interval_ms", args.get("interval"))
        if raw_interval is None:
            bail("snapshot: interval strategy requires 'interval_ms' (milliseconds)")
        try:
            interval = int(raw_interval)
        except (TypeError, ValueError):
            bail("snapshot: 'interval_ms' must be an integer number of milliseconds")
        if interval <= 0:
            bail("snapshot: 'interval_ms' must be greater than 0")
        strategy["TimeInterval"] = {"Interval": interval}
    elif strategy_type == "SpecifiedTime":
        times = args.get("times", args.get("time_ms", [0]))
        if not isinstance(times, list):
            times = [times]
        strategy["SpecifiedTime"] = {"Times": _as_int_list(times, "times", minimum=0, max_len=1000)}
    elif strategy_type == "SpecifiedFrames":
        frames = args.get("frames")
        strategy["SpecifiedFrames"] = {"Frames": _as_int_list(frames, "frames", minimum=-1)}
    else:
        raw_threshold = args.get("threshold", 0.1)
        try:
            threshold = float(raw_threshold)
        except (TypeError, ValueError):
            bail("snapshot: 'threshold' must be a float in [0, 1]")
        if not (0 <= threshold <= 1):
            bail("snapshot: 'threshold' must be in [0, 1]")
        strategy["SceneChange"] = {"Threshold": threshold}

    return strategy


def _parse_target(args: dict) -> dict:
    target = args.get("target")
    if isinstance(target, dict):
        return target

    resolution = str(args.get("resolution", "720p")).strip().lower()
    if resolution not in _VALID_RESOLUTIONS:
        bail("snapshot: 'resolution' must be one of " + ", ".join(sorted(_VALID_RESOLUTIONS)))

    target_obj: dict = {"Resolution": resolution}
    for src, dst in (("scale_long", "ScaleLong"), ("scale_short", "ScaleShort")):
        if src in args and args[src] not in (None, ""):
            try:
                n = int(args[src])
            except (TypeError, ValueError):
                bail(f"snapshot: '{src}' must be an integer")
            if not (0 <= n <= 4096):
                bail(f"snapshot: '{src}' must be in [0, 4096]")
            target_obj[dst] = n
    return target_obj


def _parse_sprite_config(args: dict) -> dict | None:
    sprite = args.get("sprite", args.get("sprite_config"))
    if sprite is None or sprite is False:
        return None
    if isinstance(sprite, dict):
        return sprite

    if not _truthy(sprite):
        return None

    cfg: dict = {"Enable": True}
    if "img_x_len" in args:
        cfg["ImgXLen"] = int(args["img_x_len"])
    if "img_y_len" in args:
        cfg["ImgYLen"] = int(args["img_y_len"])
    return cfg


def _parse_index_option(args: dict) -> dict | None:
    index_option = args.get("index_option")
    if isinstance(index_option, dict):
        return index_option

    mode = args.get("output_mode", args.get("index_mode"))
    if mode is None or mode == "":
        return None
    mode_api = str(mode).strip()
    if mode_api.lower() == "files":
        mode_api = "Files"
    elif mode_api.lower() == "index":
        mode_api = "Index"
    if mode_api not in _VALID_INDEX_MODES:
        bail("snapshot: output_mode must be Files or Index")
    return {"Mode": mode_api}


def build_snapshot_operation(args: dict) -> dict:
    """Construct OperationTaskSnapshot payload."""
    raw_snapshot = args.get("snapshot")
    if isinstance(raw_snapshot, dict):
        return raw_snapshot

    snapshot: dict = {
        "Strategy": _parse_strategy(args),
        "Target": _parse_target(args),
    }

    sprite_config = _parse_sprite_config(args)
    if sprite_config is not None:
        snapshot["SpriteConfig"] = sprite_config

    index_option = _parse_index_option(args)
    if index_option is not None:
        snapshot["IndexOption"] = index_option

    extra = args.get("snapshot_options")
    if extra is not None:
        if not isinstance(extra, dict):
            bail("snapshot: 'snapshot_options' must be an object")
        _deep_merge(snapshot, extra)

    return snapshot


def _start_execution(client, payload: dict) -> str:
    resp = client.post(_ACTION_START, _VERSION_EXEC, payload)
    result = resp.get("Result", {}) or {}
    run_id = result.get("RunId", "")
    if not run_id:
        bail(f"StartExecution did not return a RunId, response: {resp}")
    return run_id


def _store_uri_to_file_name(store_uri: str) -> str:
    if not store_uri:
        return ""
    parsed = urlparse(store_uri)
    if parsed.scheme and parsed.path:
        return parsed.path.lstrip("/")
    return store_uri


def _collect_file_like_objects(value) -> list[dict]:
    found: list[dict] = []
    if isinstance(value, dict):
        has_file = any(k in value for k in ("FileName", "StoreUri", "Url", "URI", "Uri"))
        if has_file:
            found.append(value)
        for child in value.values():
            found.extend(_collect_file_like_objects(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_collect_file_like_objects(child))
    return found


def _get_execution(client, run_id: str) -> dict:
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
    snapshot = output.get("Snapshot", {}) or {}
    image_urls: list[dict] = []

    for item in _collect_file_like_objects(snapshot):
        direct_url = (
            item.get("FileName")
            or item.get("DirectUrl")
            or _store_uri_to_file_name(item.get("StoreUri", ""))
            or item.get("Uri")
            or item.get("URI")
            or ""
        )
        signed_url = item.get("Url", "")
        if direct_url and not signed_url and space_name:
            signed_url = get_play_url_by_filename(
                client,
                space_name,
                direct_url,
                expired_minutes=int(os.environ.get("VOD_URL_EXPIRE_MINUTES", "60")),
            )

        image_urls.append(
            {
                "FileId": item.get("FileId", item.get("StoreId", "")),
                "Vid": item.get("Vid", ""),
                "DirectUrl": direct_url,
                "Source": f"directurl://{direct_url}" if direct_url else "",
                "Url": signed_url,
                "Raw": item,
            }
        )

    return {
        "Status": "Success",
        "SpaceName": space_name,
        "ImageUrls": image_urls,
        "VideoUrls": [],
        "AudioUrls": [],
        "Texts": [],
        "Snapshot": snapshot,
    }


def poll_snapshot(client, run_id: str, space_name: str) -> dict:
    for i in range(1, POLL_MAX + 1):
        log(f"Polling snapshot job [{i}/{POLL_MAX}] RunId={run_id} ...")
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
        bail("Usage: uv run python scripts/snapshot.py '<json_args>' [space_name]")

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
        bail("snapshot: the 'video' field must not be empty")

    space_name = get_space_name(argv_pos=2)
    client = get_client()

    media_input = build_media_input(asset_type, video, space_name)
    snapshot_body = build_snapshot_operation(args)

    payload = {
        "SpaceName": space_name,
        "Input": media_input,
        "Operation": {
            "Type": "Task",
            "Task": {
                "Type": "Snapshot",
                "Snapshot": snapshot_body,
            },
        },
    }

    strategy_type = (snapshot_body.get("Strategy") or {}).get("Type", "custom")
    log(f"Submitting snapshot job, video={video} type={asset_type} strategy={strategy_type}")
    try:
        run_id = _start_execution(client, payload)
    except SystemExit:
        raise
    except Exception as exc:
        bail(f"Failed to submit snapshot job: {exc}")

    log(f"Job submitted, RunId={run_id}, starting polling ...")
    out(poll_snapshot(client, run_id, space_name))


if __name__ == "__main__":
    main()
