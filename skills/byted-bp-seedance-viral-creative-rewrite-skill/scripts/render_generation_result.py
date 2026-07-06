#!/usr/bin/env python3
# Copyright (c) 2026 BytePlus. All rights reserved.
# SPDX-License-Identifier: Proprietary
"""Render the canonical generation-result frontstage response."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from media_links import media_markdown
from schemas import RewriteVideoResponse


def _language(payload: dict) -> str:
    request = payload.get("request") or {}
    language = request.get("ui_language") or "zh"
    return "en" if language == "en" else "zh"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render final video generation result.")
    parser.add_argument("--result-json", required=True, help="Generation result JSON path")
    parser.add_argument("--media-style", choices=["codex", "link", "both"], default="codex", help="Media markdown style: codex=![](path) inline (default); link=[](file:// url) clickable; both")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result_path = Path(args.result_json).expanduser().resolve()
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    language = _language(payload)
    response = RewriteVideoResponse.model_validate(payload)
    video = response.rewritten_video_local_path or response.rewritten_video_url or response.rewritten_video_remote_url
    if language == "en":
        print("Generation complete. Watch the video first:")
        if video:
            print(media_markdown("Generated video", video, style=args.media_style))
        if response.seedance_task_id:
            print(f"Task ID: {response.seedance_task_id}")
        print("Manual review checklist:")
        print("- Confirm the product identity matches the product image.")
        print("- Confirm there are no subtitles, price tags, shopping buttons, platform UI, or template brand remnants.")
        print("- Confirm the opening hook, product proof, usage/satisfaction moment, and ending are all visible.")
        print(f"Result JSON saved: {result_path}")
        return

    print("生成完成。先看成片：")
    if video:
        print(media_markdown("生成视频", video, style=args.media_style))
    if response.seedance_task_id:
        print(f"任务 ID：{response.seedance_task_id}")
    print("人工检查重点：")
    print("- 商品身份是否和商品图一致。")
    print("- 是否没有字幕、价格、购物按钮、平台 UI 或模板品牌残留。")
    print("- 开头 hook、产品证明、使用/爽点和结尾是否都清楚。")
    print(f"结果 JSON 已保存：{result_path}")


if __name__ == "__main__":
    main()
