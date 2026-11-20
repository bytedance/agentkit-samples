"""
Video merge tool (uses ffmpeg, replacing the MCP video concatenation service).

Merges the videos under videos_dir in scene_01.mp4 ~ scene_NN.mp4 order into a single complete video.
Supports smart-duration mode (each video segment may have a different duration).

Usage:
    python scripts/video_merge.py --input-dir <videos_dir> --output <output_file> --scene-count <N>
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def merge_videos(input_dir: str, output: str, scene_count: int) -> dict:
    """
    Merge scene videos in order.

    Args:
        input_dir: Directory containing the video files
        output: Output file path
        scene_count: Number of scenes

    Returns:
        dict: Merge result (status, output_path, file_size, duration_estimate)
    """
    input_dir = Path(input_dir)
    output_path = Path(output)

    # Ensure the output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build the exact file list
    file_list = []
    missing = []
    for i in range(1, scene_count + 1):
        fname = f"scene_{i:02d}.mp4"
        fpath = input_dir / fname
        if not fpath.exists():
            missing.append(fname)
        elif fpath.stat().st_size == 0:
            missing.append(f"{fname} (empty file)")
        else:
            file_list.append(str(fpath.absolute()))

    if missing:
        return {
            "status": "error",
            "message": f"Missing files: {', '.join(missing)}",
            "found": len(file_list),
            "expected": scene_count,
        }

    if len(file_list) != scene_count:
        return {
            "status": "error",
            "message": f"File count mismatch: found {len(file_list)}, expected {scene_count}",
        }

    # Create the ffmpeg concat list file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        concat_file = f.name
        for fpath in file_list:
            # The ffmpeg concat format requires escaping single quotes
            escaped = fpath.replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")

    try:
        # Merge videos using the ffmpeg concat demuxer
        cmd = [
            "ffmpeg",
            "-y",  # overwrite output
            "-f",
            "concat",  # concat demuxer
            "-safe",
            "0",  # allow absolute paths
            "-i",
            concat_file,  # input list
            "-c",
            "copy",  # copy streams directly (no re-encoding, fastest)
            str(output_path.absolute()),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5-minute timeout
        )

        if result.returncode != 0:
            # If copy mode fails, try re-encoding mode
            cmd_reencode = [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                concat_file,
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                str(output_path.absolute()),
            ]
            result = subprocess.run(
                cmd_reencode,
                capture_output=True,
                text=True,
                timeout=600,
            )

            if result.returncode != 0:
                return {
                    "status": "error",
                    "message": f"ffmpeg merge failed: {result.stderr[-500:] if result.stderr else 'unknown error'}",
                }

        # Verify the output file
        if not output_path.exists() or output_path.stat().st_size == 0:
            return {
                "status": "error",
                "message": "Output file does not exist or is empty",
            }

        file_size_mb = output_path.stat().st_size / (1024 * 1024)

        # Get the actual duration (via ffprobe)
        actual_duration = None
        try:
            probe_cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                str(output_path.absolute()),
            ]
            probe_result = subprocess.run(
                probe_cmd, capture_output=True, text=True, timeout=30
            )
            if probe_result.returncode == 0:
                probe_data = json.loads(probe_result.stdout)
                actual_duration = float(probe_data.get("format", {}).get("duration", 0))
        except Exception:
            pass

        return {
            "status": "success",
            "output_path": str(output_path.absolute()),
            "file_size_mb": round(file_size_mb, 2),
            "actual_duration_seconds": round(actual_duration, 2)
            if actual_duration
            else None,
            "scene_count": scene_count,
        }

    finally:
        # Clean up the temporary file
        try:
            os.unlink(concat_file)
        except OSError:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge scene videos")
    parser.add_argument(
        "--input-dir", required=True, help="Directory containing the video files"
    )
    parser.add_argument("--output", required=True, help="Output file path")
    parser.add_argument(
        "--scene-count", type=int, required=True, help="Number of scenes"
    )
    args = parser.parse_args()

    result = merge_videos(args.input_dir, args.output, args.scene_count)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result["status"] != "success":
        sys.exit(1)
