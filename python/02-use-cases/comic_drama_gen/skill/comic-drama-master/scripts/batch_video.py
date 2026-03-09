"""
批量视频任务管理：提交和轮询。
支持每段视频不同时长（智能时长模式）。
智能时长模式：每个分镜根据场景复杂度动态分配 4s ~ 15s 时长。
用法:
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

_VALID_DURATIONS = set(range(4, 16))
_API_BASE = "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
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
    """提交视频任务。支持统一时长或每段不同时长。

    Args:
        prompts: 提示词列表
        duration_seconds: 统一时长（当 durations 未提供时使用）
        first_frame_urls: 首帧 URL 列表（与 prompts 一一对应）
        durations: 每段时长列表（与 prompts 一一对应，优先级高于 duration_seconds）
    """
    if not (4 <= duration_seconds <= 15):
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
        # 使用每段独立时长或统一时长
        scene_duration = durations[i] if durations else duration_seconds
        if not (4 <= scene_duration <= 15):
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
        # 提交间隔：避免触发 API 并发任务数限制（ep- endpoint 通常限制同时排队任务数）
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
    parser = argparse.ArgumentParser(description="批量视频任务管理")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # submit 子命令
    submit_parser = subparsers.add_parser("submit", help="批量提交视频任务")
    submit_parser.add_argument(
        "--prompts-file", required=True, help="JSON 文件，包含 prompts 列表"
    )
    submit_parser.add_argument(
        "--first-frames-file", default=None, help="JSON 文件，包含首帧 URL 列表"
    )
    submit_parser.add_argument(
        "--duration",
        type=int,
        default=10,
        help="统一视频时长（秒），当 --durations-file 未提供时使用",
    )
    submit_parser.add_argument(
        "--durations-file",
        default=None,
        help="JSON 文件，包含每段时长列表（与 prompts 一一对应）",
    )

    # poll 子命令
    poll_parser = subparsers.add_parser("poll", help="轮询等待任务完成")
    poll_parser.add_argument(
        "--task-ids-file",
        required=True,
        help="JSON 文件，包含 {scene_key: task_id} 字典",
    )
    poll_parser.add_argument("--interval", type=int, default=30, help="轮询间隔（秒）")

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
