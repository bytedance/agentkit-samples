"""
创建单个视频生成任务。

用法:
    python scripts/create_video_task.py --prompt "<prompt>" [--duration 10] [--first-frame "<url>"] [--last-frame "<url>"]
"""

import argparse
import json
import logging
import os
import re
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_VALID_DURATIONS = set(range(4, 16))
_API_URL = "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
_MODEL = os.environ.get("DEFAULT_VIDEO_MODEL_NAME") or os.environ.get(
    "MODEL_VIDEO_NAME"
)


def _get_auth() -> str:
    api_key = os.environ.get("ARK_API_KEY", "") or os.environ.get(
        "MODEL_AGENT_API_KEY", ""
    )
    return f"Bearer {api_key}"


def _strip_cli_flags(prompt: str) -> str:
    return re.sub(r"\s*--\w+\s+\S+", "", prompt).strip()


def _build_content(
    prompt: str,
    first_frame_image_url: Optional[str],
    last_frame_image_url: Optional[str],
) -> list:
    content = []
    if first_frame_image_url and last_frame_image_url:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": first_frame_image_url},
                "role": "first_frame",
            }
        )
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": last_frame_image_url},
                "role": "last_frame",
            }
        )
    elif first_frame_image_url:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": first_frame_image_url},
                "role": "first_frame",
            }
        )
    content.append({"type": "text", "text": _strip_cli_flags(prompt)})
    return content


def create_video_task(
    prompt: str,
    duration_seconds: int = 10,
    first_frame_image_url: Optional[str] = None,
    last_frame_image_url: Optional[str] = None,
) -> str:
    if duration_seconds not in _VALID_DURATIONS:
        duration_seconds = 10

    logger.info(f"Using video generation model: {_MODEL}")
    headers = {"Content-Type": "application/json", "Authorization": _get_auth()}
    payload = {
        "model": _MODEL,
        "content": _build_content(prompt, first_frame_image_url, last_frame_image_url),
        "seed": -1,
        "duration": duration_seconds,
        "watermark": False,
    }

    try:
        resp = requests.post(_API_URL, json=payload, headers=headers, timeout=30)
        logger.info(
            f"create_video_task status={resp.status_code} body={resp.text[:300]}"
        )
        resp.raise_for_status()

        task_id = resp.json().get("id")
        if not task_id:
            raise ValueError(f"响应缺少 task_id: {resp.text}")

        logger.info(f"任务已提交 task_id={task_id} duration={duration_seconds}s")
        return task_id

    except requests.exceptions.RequestException as e:
        body = getattr(getattr(e, "response", None), "text", "")
        raise Exception(f"提交视频任务失败: {e} | 响应: {body}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="创建视频生成任务")
    parser.add_argument("--prompt", required=True, help="视频提示词")
    parser.add_argument("--duration", type=int, default=10, help="时长（秒）")
    parser.add_argument("--first-frame", default=None, help="首帧图片 URL")
    parser.add_argument("--last-frame", default=None, help="尾帧图片 URL")
    args = parser.parse_args()

    task_id = create_video_task(
        prompt=args.prompt,
        duration_seconds=args.duration,
        first_frame_image_url=args.first_frame,
        last_frame_image_url=args.last_frame,
    )
    print(json.dumps({"task_id": task_id}, ensure_ascii=False))
