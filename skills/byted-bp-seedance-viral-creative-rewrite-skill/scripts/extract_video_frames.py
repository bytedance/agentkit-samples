#!/usr/bin/env python3
# Copyright (c) 2026 BytePlus. All rights reserved.
# SPDX-License-Identifier: Proprietary
"""Extract timestamped video frames for agent-led template understanding."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from dependency_check import ensure_analysis_dependencies

BASE_DIR = Path(__file__).resolve().parent.parent


def find_ffmpeg() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            return ffmpeg
    raise RuntimeError(
        "No ffmpeg executable found. Install requirements.txt so imageio-ffmpeg is available."
    )


def extract_audio_track(video_path: Path, output_dir: Path, *, ffmpeg: str) -> dict:
    """Export a mono 16k audio clip so the agent can actually listen to the template.

    Returns audio info for the manifest. If the video has no audio stream (e.g. a
    silent screen recording) or extraction fails, this is non-fatal: it records
    has_audio_stream=False instead of raising, so frame extraction still succeeds.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    audio_path = output_dir / "audio_track.m4a"
    if audio_path.exists():
        audio_path.unlink()
    cmd = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        str(audio_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode == 0 and audio_path.exists() and audio_path.stat().st_size > 0:
        return {"has_audio_stream": True, "audio_path": str(audio_path)}
    # No audio stream, or extraction failed: clean up any partial file and record the fact.
    if audio_path.exists():
        try:
            audio_path.unlink()
        except OSError:
            pass
    return {
        "has_audio_stream": False,
        "audio_path": None,
        "audio_note": (proc.stderr or "").strip()[:300] or "no audio stream detected",
    }


def build_contact_sheet(frame_paths: list[Path], out_path: Path, *, columns: int = 5) -> None:
    from PIL import Image, ImageDraw

    if not frame_paths:
        raise RuntimeError("No frames available for contact sheet.")
    images = [Image.open(path).convert("RGB") for path in frame_paths]
    tile_w = max(image.width for image in images)
    tile_h = max(image.height for image in images) + 24
    rows = (len(images) + columns - 1) // columns
    sheet = Image.new("RGB", (tile_w * columns, tile_h * rows), "white")
    draw = ImageDraw.Draw(sheet)
    for idx, image in enumerate(images):
        x = (idx % columns) * tile_w + (tile_w - image.width) // 2
        y = (idx // columns) * tile_h
        sheet.paste(image, (x, y))
        draw.text(((idx % columns) * tile_w + 6, y + image.height + 4), f"t={idx}s", fill=(0, 0, 0))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, quality=92)


def extract_frames(video_path: Path, output_dir: Path, *, fps: float, max_frames: int, width: int, with_audio: bool = True) -> dict:
    ffmpeg = find_ffmpeg()
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_pattern = output_dir / "frame_raw_%04d.jpg"
    cmd = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-vf",
        f"fps={fps},scale={width}:-1",
        "-frames:v",
        str(max_frames),
        str(raw_pattern),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    raw_frames = sorted(output_dir.glob("frame_raw_*.jpg"))
    if not raw_frames:
        raise RuntimeError(f"No frames extracted from {video_path}")

    frames: list[dict] = []
    final_paths: list[Path] = []
    for index, raw_path in enumerate(raw_frames):
        timestamp_sec = index / fps
        final_path = output_dir / f"frame_{index:04d}_t{timestamp_sec:06.2f}s.jpg"
        if final_path.exists():
            final_path.unlink()
        raw_path.rename(final_path)
        final_paths.append(final_path)
        frames.append(
            {
                "index": index,
                "timestamp_sec": round(timestamp_sec, 3),
                "path": str(final_path),
            }
        )

    contact_sheet = output_dir / "contact_sheet_1fps.jpg"
    build_contact_sheet(final_paths, contact_sheet)
    audio_info = {"has_audio_stream": None, "audio_path": None}
    if with_audio:
        try:
            audio_info = extract_audio_track(video_path, output_dir, ffmpeg=ffmpeg)
        except Exception as exc:  # never let audio extraction break frame extraction
            audio_info = {"has_audio_stream": False, "audio_path": None, "audio_note": f"audio extraction error: {exc}"[:300]}
    manifest = {
        "video_path": str(video_path),
        "sample_fps": fps,
        "max_frames": max_frames,
        "frame_count": len(frames),
        "frames": frames,
        "contact_sheet": str(contact_sheet),
        "ffmpeg": ffmpeg,
        **audio_info,
    }
    manifest_path = output_dir / "frames_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract 1fps frames for viral template understanding.")
    parser.add_argument("video", help="Local template video path")
    parser.add_argument("--output-dir", required=True, help="Directory for frames, contact sheet, and manifest")
    parser.add_argument("--fps", type=float, default=1.0, help="Sampling FPS. Default: 1.0")
    parser.add_argument("--max-frames", type=int, default=15, help="Maximum frames to extract. Default: 15")
    parser.add_argument("--width", type=int, default=512, help="Frame width after scaling. Default: 512")
    parser.add_argument(
        "--with-audio",
        dest="with_audio",
        action="store_true",
        help="Export a mono 16k audio_track.m4a so the agent can listen for voiceover vs music-only (default: on).",
    )
    parser.add_argument(
        "--no-audio",
        dest="with_audio",
        action="store_false",
        help="Skip audio export.",
    )
    parser.set_defaults(with_audio=True)
    args = parser.parse_args()

    ensure_analysis_dependencies(base_dir=BASE_DIR)
    video_path = Path(args.video).expanduser().resolve()
    if not video_path.is_file():
        raise SystemExit(f"Video file not found: {video_path}")
    manifest = extract_frames(
        video_path,
        Path(args.output_dir).expanduser().resolve(),
        fps=args.fps,
        max_frames=args.max_frames,
        width=args.width,
        with_audio=args.with_audio,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
