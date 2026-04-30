#!/usr/bin/env python3
# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     `http://www.apache.org/licenses/LICENSE-2.0`
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
为 byted-mediakit-videoedit 生成的剪辑视频叠加花字特效。

用法：
  python video_effects.py <video> <effects_config.json> <effects_dir> [output.mp4]

参数：
  video             剪辑后的视频文件路径
  effects_config    特效配置 JSON 文件路径（时间轴相对于剪辑视频）
  effects_dir       Remotion 渲染输出目录（包含 .mov 特效文件）
  output            输出文件路径（默认：output_with_effects.mp4）
"""

import json
import sys
import os
import argparse
import subprocess
from pathlib import Path
from shutil import which


def process_video(video_path, config_path, effects_dir, output_path):
    print(f"🎬 正在合成特效视频: {video_path}")

    if not os.path.exists(video_path):
        print(f"❌ 错误: 视频文件不存在: {video_path}")
        sys.exit(1)

    if not os.path.exists(config_path):
        print(f"❌ 错误: 配置文件不存在: {config_path}")
        sys.exit(1)

    if not os.path.exists(effects_dir):
        print(f"❌ 错误: 特效目录不存在: {effects_dir}")
        sys.exit(1)

    if which("ffmpeg") is None:
        print("❌ 错误: ffmpeg 不可用，请先安装：brew install ffmpeg")
        sys.exit(1)

    print("📋 加载特效配置...")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    effects = _collect_effects(config, effects_dir)
    if not effects:
        print("⚠️  未发现可叠加的特效文件，直接复制原视频")
        _copy_file(video_path, output_path)
        return

    print(f"🎞️  叠加特效 ({len(effects)} 个)...")
    _render_overlay(video_path, effects, output_path)
    print("✅ 特效合成完成！")
    print(f"📁 输出文件: {output_path}")


def _copy_file(src, dst):
    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    with open(src, "rb") as f_in, open(dst, "wb") as f_out:
        f_out.write(f_in.read())


def _collect_effects(config, effects_dir):
    """收集所有特效条目，返回 [{path, start, end}, ...] 列表。"""
    effects = []

    def add(path, start_ms, duration_ms):
        if path and os.path.exists(path) and duration_ms and duration_ms > 0:
            effects.append(
                {
                    "path": path,
                    "start": start_ms / 1000.0,
                    "end": (start_ms + duration_ms) / 1000.0,
                }
            )

    for i, ch in enumerate(config.get("chapterTitles", [])):
        add(
            os.path.join(effects_dir, f"chapterTitles-{i}.mov"),
            ch.get("startMs", 0),
            ch.get("durationMs", 3000),
        )

    for i, phrase in enumerate(config.get("keyPhrases", [])):
        duration_ms = phrase.get("durationMs")
        if duration_ms is None:
            start_ms = phrase.get("startMs", 0)
            end_ms = phrase.get("endMs")
            duration_ms = max((end_ms or start_ms) - start_ms, 0)
        add(
            os.path.join(effects_dir, f"keyPhrases-{i}.mov"),
            phrase.get("startMs", 0),
            duration_ms,
        )

    for i, lt in enumerate(config.get("lowerThirds", [])):
        add(
            os.path.join(effects_dir, f"lowerThirds-{i}.mov"),
            lt.get("startMs", 0),
            lt.get("durationMs", 5000),
        )

    for i, quote in enumerate(config.get("quotes", [])):
        add(
            os.path.join(effects_dir, f"quotes-{i}.mov"),
            quote.get("startMs", 0),
            quote.get("durationMs", 5000),
        )

    for i, burst in enumerate(config.get("danmakuBursts", [])):
        add(
            os.path.join(effects_dir, f"danmakuBursts-{i}.mov"),
            burst.get("startMs", 0),
            burst.get("durationMs", 3000),
        )

    return effects


def _build_filter_complex(effects):
    filters = ["[0:v]format=rgba[base]"]
    last_label = "base"
    for idx, effect in enumerate(effects):
        start = effect["start"]
        end = effect["end"]
        ov_label = f"ov{idx}"
        out_label = f"v{idx + 1}"
        filters.append(
            f"[{idx + 1}:v]setpts=PTS-STARTPTS+{start}/TB,format=rgba[{ov_label}]"
        )
        filters.append(
            f"[{last_label}][{ov_label}]overlay="
            f"enable='between(t,{start},{end})':format=auto[{out_label}]"
        )
        last_label = out_label
    return ";".join(filters), last_label


def _render_overlay(video_path, effects, output_path):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    filter_complex, last_label = _build_filter_complex(effects)
    filter_complex = f"{filter_complex};[{last_label}]format=yuv420p[outv]"

    cmd = ["ffmpeg", "-y", "-i", video_path]
    for e in effects:
        cmd.extend(["-i", e["path"]])
    cmd.extend(
        [
            "-filter_complex",
            filter_complex,
            "-map",
            "[outv]",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-crf",
            "18",
            "-preset",
            "fast",
            "-c:a",
            "aac",
            "-movflags",
            "faststart",
            output_path,
        ]
    )

    subprocess.run(cmd, check=True)


def main():
    parser = argparse.ArgumentParser(
        description="为 bilibili 剪辑视频叠加花字特效",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例（位置参数）:
  python video_effects.py output_cut.mp4 temp/effects_config.json temp/effects output_final.mp4

示例（命名参数）:
  python video_effects.py --input output_cut.mp4 --config temp/effects_config.json --effects-dir temp/effects --output output_final.mp4
        """,
    )
    # 位置参数（兼容旧用法）
    parser.add_argument("video", nargs="?", default=None, help="剪辑后的视频文件路径")
    parser.add_argument(
        "config", nargs="?", default=None, help="特效配置 JSON 文件路径"
    )
    parser.add_argument(
        "effects_dir", nargs="?", default=None, help="Remotion 渲染的特效 .mov 文件目录"
    )
    parser.add_argument("output", nargs="?", default=None, help="输出视频路径")
    # 命名参数（--flag 形式）
    parser.add_argument(
        "--input", dest="input_flag", default=None, help="剪辑后的视频文件路径"
    )
    parser.add_argument(
        "--config", dest="config_flag", default=None, help="特效配置 JSON 文件路径"
    )
    parser.add_argument(
        "--effects-dir",
        dest="effects_dir_flag",
        default=None,
        help="Remotion 渲染的特效 .mov 文件目录",
    )
    parser.add_argument(
        "--output", dest="output_flag", default=None, help="输出视频路径"
    )
    args = parser.parse_args()

    # 命名参数优先，回退到位置参数
    video_arg = args.input_flag or args.video
    config_arg = args.config_flag or args.config
    effects_dir_arg = args.effects_dir_flag or args.effects_dir
    output_arg = args.output_flag or args.output

    if not video_arg or not config_arg or not effects_dir_arg:
        parser.error(
            "必须提供 video、config、effects_dir（位置参数或 --input/--config/--effects-dir）"
        )

    original_cwd = os.environ.get("ORIGINAL_CWD", os.getcwd())
    if output_arg:
        output_path = output_arg
        if not os.path.isabs(output_path):
            output_path = os.path.join(original_cwd, output_path)
    else:
        stem = Path(video_arg).stem
        output_path = os.path.join(original_cwd, f"{stem}_with_effects.mp4")

    try:
        process_video(video_arg, config_arg, effects_dir_arg, output_path)
    except Exception as e:
        print(f"❌ 处理失败: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
