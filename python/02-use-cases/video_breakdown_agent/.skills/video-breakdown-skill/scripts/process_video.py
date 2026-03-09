"""
视频预处理脚本（独立可执行）。
自包含视频预处理，无需外部后端服务。
需要本机安装 FFmpeg。

Usage:
    python scripts/process_video.py "<video_url>"

Env:
    FFMPEG_BIN, FFPROBE_BIN, VOLCENGINE_ACCESS_KEY, VOLCENGINE_SECRET_KEY,
    VOLC_ASR_APP_ID, VOLC_ASR_ACCESS_KEY, VOLC_ASR_RESOURCE_ID,
    DATABASE_TOS_BUCKET (或 TOS_BUCKET), DATABASE_TOS_REGION (或 TOS_REGION)
"""

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import httpx


def _run_command(cmd: List[str]) -> str:
    process = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
    )
    return process.stdout.strip()


def _probe_video(ffprobe_bin: str, video_path: Path) -> Dict[str, Any]:
    cmd = [
        ffprobe_bin,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(video_path),
    ]
    result = _run_command(cmd)
    info = json.loads(result) if result else {}
    fmt = info.get("format") or {}
    duration = float(fmt.get("duration", 0))
    w, h, fr = None, None, None
    for s in info.get("streams", []):
        if s.get("codec_type") == "video":
            w, h, fr = s.get("width"), s.get("height"), s.get("r_frame_rate")
            break
    return {
        "duration": duration,
        "width": w,
        "height": h,
        "frame_rate": fr,
        "size": fmt.get("size"),
    }


def _build_segments(duration: float):
    segments = []
    idx = 1
    bps = [0.0, 3.0, 5.0, 10.0, 20.0]
    for i in range(len(bps) - 1):
        if duration <= bps[i]:
            break
        end = min(bps[i + 1], duration)
        if end - bps[i] < 0.5:
            break
        segments.append({"index": idx, "start": bps[i], "end": end})
        idx += 1
    if duration > 20.0:
        c = 20.0
        while c < duration:
            e = min(duration, c + 10.0)
            if e - c < 0.5:
                break
            segments.append({"index": idx, "start": c, "end": e})
            idx += 1
            c = e
    return segments


def _extract_frames(ffmpeg_bin: str, video_path: Path, segments, fps=3):
    frames_dir = video_path.parent / "frames"
    frames_dir.mkdir(exist_ok=True)
    for seg in segments:
        seg["frame_paths"] = []
        dur = seg["end"] - seg["start"]
        for i in range(fps):
            ratio = i / max(fps - 1, 1)
            offset = min(seg["start"] + ratio * dur, seg["end"] - 0.1)
            offset = max(offset, seg["start"])
            out = frames_dir / f"seg{seg['index']:03d}_frame_{i}.jpg"
            cmd = [
                ffmpeg_bin,
                "-y",
                "-ss",
                f"{offset:.2f}",
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-q:v",
                "5",
                str(out),
            ]
            try:
                _run_command(cmd)
                if out.exists():
                    seg["frame_paths"].append(str(out))
            except Exception:
                pass


async def main(video_url: str):
    ffmpeg_bin = os.getenv("FFMPEG_BIN", "ffmpeg")
    ffprobe_bin = os.getenv("FFPROBE_BIN", "ffprobe")
    temp_dir = Path(tempfile.mkdtemp(prefix="vba_"))
    task_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    local_video = temp_dir / f"{task_id}.mp4"

    try:
        # Download
        print("[1/4] 下载视频...", file=sys.stderr)
        async with httpx.AsyncClient(timeout=300, follow_redirects=True) as c:
            r = await c.get(video_url)
            r.raise_for_status()
            local_video.write_bytes(r.content)

        # Metadata
        print("[2/4] 提取元数据...", file=sys.stderr)
        meta = _probe_video(ffprobe_bin, local_video)
        dur = meta["duration"]
        if dur <= 0:
            print(json.dumps({"error": "无法获取视频时长"}))
            return

        # Segments
        print(f"[3/4] 构建分镜 ({dur:.1f}s)...", file=sys.stderr)
        segments = _build_segments(dur)

        # Frames
        print("[4/4] 提取关键帧...", file=sys.stderr)
        _extract_frames(ffmpeg_bin, local_video, segments)

        result = {
            "task_id": task_id,
            "duration": round(dur, 2),
            "resolution": f"{meta.get('width')}x{meta.get('height')}",
            "segment_count": len(segments),
            "segments": [
                {
                    "index": s["index"],
                    "start": round(s["start"], 2),
                    "end": round(s["end"], 2),
                    "frame_paths": s.get("frame_paths", []),
                }
                for s in segments
            ],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python process_video.py <video_url>", file=sys.stderr)
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
