"""
Batch video task management: submission and polling.
Supports a different duration per video segment (smart duration mode).
Smart duration mode: each storyboard shot is dynamically assigned a duration of 4s ~ 30s based on scene complexity.
Usage:
    python scripts/batch_video.py submit --prompts-file prompts.json [--first-frames-file frames.json] [--duration 10] [--durations-file durations.json]
    python scripts/batch_video.py poll --task-ids-file task_ids.json [--interval 30]
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_VALID_DURATIONS = set(range(4, 31))
_API_BASE = (
    os.environ.get(
        "MODEL_VIDEO_API_BASE", "https://ark.ap-southeast.bytepluses.com/api/v3"
    ).rstrip("/")
    + "/contents/generations/tasks"
)
_MODEL = os.environ.get("DEFAULT_VIDEO_MODEL_NAME") or os.environ.get(
    "MODEL_VIDEO_NAME"
)


def _get_auth() -> str:
    api_key = os.environ.get("ARK_API_KEY", "") or os.environ.get(
        "MODEL_AGENT_API_KEY", ""
    )
    return f"Bearer {api_key}"


def _get_headers() -> dict:
    return {"Content-Type": "application/json", "Authorization": _get_auth()}


def _strip_cli_flags(prompt: str) -> str:
    return re.sub(r"\s*--\w+\s+\S+", "", prompt).strip()


def _build_content(prompt: str, first_frame_image_url: Optional[str]) -> list:
    content = []
    if first_frame_image_url:
        content.append(
            {"type": "image_url", "image_url": {"url": first_frame_image_url}}
        )
    content.append({"type": "text", "text": _strip_cli_flags(prompt)})
    return content


def submit_video_tasks(
    prompts: list,
    duration_seconds: int = 10,
    first_frame_urls: Optional[list] = None,
    durations: Optional[list] = None,
) -> dict:
    """Submit video tasks. Supports a uniform duration or a different duration per segment.

    Args:
        prompts: List of prompts
        duration_seconds: Uniform duration (used when durations is not provided)
        first_frame_urls: List of first-frame URLs (one-to-one with prompts)
        durations: List of per-segment durations (one-to-one with prompts, takes precedence over duration_seconds)
    """
    if not (4 <= duration_seconds <= 30):
        duration_seconds = 10

    if first_frame_urls and len(first_frame_urls) != len(prompts):
        first_frame_urls = None

    if durations and len(durations) != len(prompts):
        durations = None

    headers = _get_headers()
    task_ids = {}
    errors = {}
    logger.info(f"Using video generation model: {_MODEL}")
    for i, prompt in enumerate(prompts):
        scene_key = f"scene_{i + 1:02d}"
        frame_url = first_frame_urls[i] if first_frame_urls else None
        # Use per-segment duration or uniform duration
        scene_duration = durations[i] if durations else duration_seconds
        if not (4 <= scene_duration <= 30):
            scene_duration = 10
        payload = {
            "model": _MODEL,
            "content": _build_content(prompt, frame_url),
            "seed": -1,
            "duration": scene_duration,
            "watermark": False,
        }
        try:
            resp = requests.post(_API_BASE, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            task_id = resp.json().get("id")
            if not task_id:
                raise ValueError(f"no task_id in response: {resp.text[:200]}")
            task_ids[scene_key] = task_id
            logger.info(
                f"submitted {scene_key} task_id={task_id} duration={scene_duration}s"
            )
        except Exception as e:
            errors[scene_key] = str(e)
            logger.error(f"failed to submit {scene_key}: {e}")
        # Submission interval: avoids hitting the API's concurrent task limit (ep- endpoints usually limit the number of simultaneously queued tasks)
        time.sleep(2)

    return {"submitted": task_ids, "errors": errors, "total": len(prompts)}


def poll_video_tasks(task_ids: dict, poll_interval_seconds: int = 30) -> dict:
    pending = dict(task_ids)
    results = {}
    failed = {}
    max_rounds = 60
    headers = _get_headers()

    for round_num in range(max_rounds):
        if not pending:
            break
        time.sleep(poll_interval_seconds)
        still_pending = {}
        for scene_key, task_id in pending.items():
            try:
                resp = requests.get(
                    f"{_API_BASE}/{task_id}", headers=headers, timeout=30
                )
                resp.raise_for_status()
                data = resp.json()
                status = data.get("status", "")
                if status in ("success", "succeeded"):
                    video_url = _extract_video_url(data)
                    if video_url:
                        results[scene_key] = video_url
                        logger.info(f"{scene_key} done: {video_url[:80]}")
                    else:
                        failed[scene_key] = f"success but no video_url: {data}"
                elif status == "failed":
                    failed[scene_key] = data.get("error", "unknown failure")
                    logger.error(f"{scene_key} failed: {failed[scene_key]}")
                else:
                    still_pending[scene_key] = task_id
            except Exception as e:
                still_pending[scene_key] = task_id
                logger.warning(f"poll error for {scene_key}: {e}")
        pending = still_pending
        if pending:
            print(
                f"[poll round {round_num + 1}] completed={len(results)} pending={len(pending)} failed={len(failed)}",
                file=sys.stderr,
            )

    if pending:
        for scene_key in pending:
            failed[scene_key] = "timeout after 30 minutes"

    return {"completed": results, "failed": failed, "pending": list(pending.keys())}


def _extract_video_url(data: dict) -> Optional[str]:
    content = data.get("content", {})
    if isinstance(content, dict):
        for key in ("video_url", "url", "url_main"):
            if content.get(key):
                return content[key]
        for val in content.values():
            if (
                isinstance(val, str)
                and "http" in val
                and (".mp4" in val or "video" in val.lower())
            ):
                return val
    elif isinstance(content, list):
        for c in content:
            if isinstance(c, dict):
                for key in ("video_url", "url", "url_main"):
                    if c.get(key):
                        return c[key]
    return data.get("video_url") or data.get("url")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch video task management")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # submit subcommand
    submit_parser = subparsers.add_parser("submit", help="Submit video tasks in batch")
    submit_parser.add_argument(
        "--prompts-file", required=True, help="JSON file containing the list of prompts"
    )
    submit_parser.add_argument(
        "--first-frames-file",
        default=None,
        help="JSON file containing the list of first-frame URLs",
    )
    submit_parser.add_argument(
        "--duration",
        type=int,
        default=10,
        help="Uniform video duration (seconds), used when --durations-file is not provided",
    )
    submit_parser.add_argument(
        "--durations-file",
        default=None,
        help="JSON file containing the list of per-segment durations (one-to-one with prompts)",
    )

    # poll subcommand
    poll_parser = subparsers.add_parser(
        "poll", help="Poll and wait for task completion"
    )
    poll_parser.add_argument(
        "--task-ids-file",
        required=True,
        help="JSON file containing a {scene_key: task_id} dictionary",
    )
    poll_parser.add_argument(
        "--interval", type=int, default=30, help="Polling interval (seconds)"
    )

    args = parser.parse_args()

    if args.command == "submit":
        with open(args.prompts_file, "r", encoding="utf-8") as f:
            prompts = json.load(f)

        first_frames = None
        if args.first_frames_file:
            with open(args.first_frames_file, "r", encoding="utf-8") as f:
                first_frames = json.load(f)

        durations = None
        if args.durations_file:
            with open(args.durations_file, "r", encoding="utf-8") as f:
                durations = json.load(f)

        result = submit_video_tasks(prompts, args.duration, first_frames, durations)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "poll":
        with open(args.task_ids_file, "r", encoding="utf-8") as f:
            task_ids = json.load(f)

        result = poll_video_tasks(task_ids, args.interval)
        print(json.dumps(result, ensure_ascii=False, indent=2))
