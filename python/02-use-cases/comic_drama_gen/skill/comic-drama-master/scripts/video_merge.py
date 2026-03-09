"""
视频合并工具（使用 ffmpeg，替代 MCP 视频拼接服务）。

将 videos_dir 下按 scene_01.mp4 ~ scene_NN.mp4 顺序合并为一个完整视频。
支持智能时长模式（每段视频时长可能不同）。

用法:
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
    按顺序合并分镜视频。

    Args:
        input_dir: 视频文件目录
        output: 输出文件路径
        scene_count: 场景数量

    Returns:
        dict: 合并结果（status, output_path, file_size, duration_estimate）
    """
    input_dir = Path(input_dir)
    output_path = Path(output)

    # 确保输出目录存在
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 构建精确文件列表
    file_list = []
    missing = []
    for i in range(1, scene_count + 1):
        fname = f"scene_{i:02d}.mp4"
        fpath = input_dir / fname
        if not fpath.exists():
            missing.append(fname)
        elif fpath.stat().st_size == 0:
            missing.append(f"{fname} (空文件)")
        else:
            file_list.append(str(fpath.absolute()))

    if missing:
        return {
            "status": "error",
            "message": f"缺失文件: {', '.join(missing)}",
            "found": len(file_list),
            "expected": scene_count,
        }

    if len(file_list) != scene_count:
        return {
            "status": "error",
            "message": f"文件数量不匹配: 找到 {len(file_list)} 个，期望 {scene_count} 个",
        }

    # 创建 ffmpeg concat 列表文件
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        concat_file = f.name
        for fpath in file_list:
            # ffmpeg concat 格式要求转义单引号
            escaped = fpath.replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")

    try:
        # 使用 ffmpeg concat demuxer 合并视频
        cmd = [
            "ffmpeg",
            "-y",  # 覆盖输出
            "-f",
            "concat",  # concat demuxer
            "-safe",
            "0",  # 允许绝对路径
            "-i",
            concat_file,  # 输入列表
            "-c",
            "copy",  # 直接复制流（无重编码，速度最快）
            str(output_path.absolute()),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5分钟超时
        )

        if result.returncode != 0:
            # 如果 copy 模式失败，尝试重编码模式
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
                    "message": f"ffmpeg 合并失败: {result.stderr[-500:] if result.stderr else 'unknown error'}",
                }

        # 验证输出文件
        if not output_path.exists() or output_path.stat().st_size == 0:
            return {
                "status": "error",
                "message": "输出文件不存在或为空",
            }

        file_size_mb = output_path.stat().st_size / (1024 * 1024)

        # 获取实际时长（通过 ffprobe）
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
        # 清理临时文件
        try:
            os.unlink(concat_file)
        except OSError:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="合并分镜视频")
    parser.add_argument("--input-dir", required=True, help="视频文件目录")
    parser.add_argument("--output", required=True, help="输出文件路径")
    parser.add_argument("--scene-count", type=int, required=True, help="场景数量")
    args = parser.parse_args()

    result = merge_videos(args.input_dir, args.output, args.scene_count)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result["status"] != "success":
        sys.exit(1)
