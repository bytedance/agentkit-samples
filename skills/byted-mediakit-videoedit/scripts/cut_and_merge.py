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
根据 clips JSON 使用 FFmpeg 截取视频片段、添加转场效果并合并输出。

clips JSON 格式：
{
  "clips": [
    {
      "video_file": "/path/to/video.mp4",
      "start": 125.3,
      "end": 142.8,
      "reason": "说明为什么截取这段"
    },
    ...
  ],
  "transition": "fade",          // 转场类型，默认 "none"
  "transition_duration": 0.5,    // 转场时长（秒），默认 0.5
  "output_path": "/tmp/output.mp4"
}

支持的转场效果（需要 FFmpeg xfade filter）：
  none, fade, dissolve, wipeleft, wiperight, slideup, slidedown,
  zoomin, circleopen, pixelize, radial, smoothleft
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


SUPPORTED_TRANSITIONS = {
    'none', 'fade', 'dissolve', 'wipeleft', 'wiperight', 'slideup', 'slidedown',
    'zoomin', 'circleopen', 'pixelize', 'radial', 'smoothleft'
}


def check_ffmpeg():
    """检查 FFmpeg 是否可用。"""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def get_video_duration(video_path: str) -> float:
    """获取视频时长（秒）。"""
    result = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', video_path],
        capture_output=True, text=True
    )
    try:
        info = json.loads(result.stdout)
        return float(info['format']['duration'])
    except (json.JSONDecodeError, KeyError, ValueError):
        return float('inf')


def extract_clip(video_file: str, start: float, end: float, output_path: str,
                 video_duration: float = None) -> bool:
    """用 FFmpeg 截取视频片段。"""
    if video_duration is None:
        video_duration = get_video_duration(video_file)

    # 安全边界处理
    start = max(0.0, start)
    end = min(end, video_duration)
    if start >= end:
        print(f"  [警告] 片段时间无效 ({start:.1f}s - {end:.1f}s)，跳过")
        return False

    duration = end - start
    cmd = [
        'ffmpeg', '-y',
        '-ss', str(start),
        '-i', video_file,
        '-t', str(duration),
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-r', '30',
        '-c:a', 'aac', '-b:a', '192k', '-ar', '44100', '-ac', '2',
        '-avoid_negative_ts', 'make_zero',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [错误] FFmpeg 截取失败:\n{result.stderr[-500:]}")
        return False
    return True


def merge_clips_simple(clip_paths: list[str], output_path: str) -> bool:
    """简单拼接（无转场），使用 concat demuxer。"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        list_file = f.name
        for cp in clip_paths:
            f.write(f"file '{cp}'\n")

    cmd = [
        'ffmpeg', '-y',
        '-f', 'concat', '-safe', '0', '-i', list_file,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'aac', '-b:a', '192k',
        '-avoid_negative_ts', 'make_zero',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    os.unlink(list_file)
    if result.returncode != 0:
        print(f"  [错误] 合并失败:\n{result.stderr[-500:]}")
        return False
    return True


def get_video_resolution(video_path: str) -> tuple[int, int]:
    """获取视频分辨率 (width, height)，失败返回 (0, 0)。"""
    result = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-select_streams', 'v:0',
         '-show_entries', 'stream=width,height', '-of', 'json', video_path],
        capture_output=True, text=True
    )
    try:
        stream = json.loads(result.stdout)['streams'][0]
        return int(stream['width']), int(stream['height'])
    except (json.JSONDecodeError, KeyError, IndexError, ValueError):
        return (0, 0)


def compute_optimal_resolution(resolutions: list[tuple[int, int]]) -> tuple[int, int]:
    """从各片段分辨率列表中选出最优输出分辨率。

    对每个候选分辨率（取自各片段实际分辨率的去重集合），计算将所有片段
    按比例缩放后的黑边总面积；选总黑边最小的，同等时优先选面积较大的。
    确保宽高均为偶数（libx264 要求）。
    """
    valid = [(w, h) for w, h in resolutions if w > 0 and h > 0]
    if not valid:
        return (1920, 1080)

    candidates = list(set(valid))
    best_res = candidates[0]
    best_waste = float('inf')

    for tw, th in candidates:
        total_waste = 0
        for w, h in valid:
            scale = min(tw / w, th / h)
            total_waste += tw * th - int(w * scale) * int(h * scale)
        if total_waste < best_waste or (
            total_waste == best_waste and tw * th > best_res[0] * best_res[1]
        ):
            best_waste = total_waste
            best_res = (tw, th)

    w, h = best_res
    return (w + w % 2, h + h % 2)


def normalize_clip_resolution(clip_path: str, output_path: str,
                               target_w: int, target_h: int) -> bool:
    """将片段缩放并填充黑边至目标分辨率，保持原始宽高比。
    若分辨率已匹配则直接复制，不重新编码。
    """
    w, h = get_video_resolution(clip_path)
    if (w, h) == (target_w, target_h):
        shutil.copy(clip_path, output_path)
        return True

    vf = (
        f'scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,'
        f'pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:color=black'
    )
    cmd = [
        'ffmpeg', '-y', '-i', clip_path,
        '-vf', vf,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'aac', '-b:a', '192k', '-ar', '44100', '-ac', '2',
        '-avoid_negative_ts', 'make_zero',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"    [警告] 分辨率归一化失败，使用原始片段:\n{result.stderr[-200:]}")
        shutil.copy(clip_path, output_path)
    return True


def analyze_loudness(clip_path: str) -> dict | None:
    """第一遍：用 loudnorm 分析片段的响度统计数据（EBU R128）。结果在 stderr JSON 块中。"""
    cmd = [
        'ffmpeg', '-y', '-i', clip_path,
        '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json',
        '-f', 'null', '-'
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    stderr = result.stderr
    # loudnorm 将 JSON 输出到 stderr，取最后一个完整的 {} 块
    start = stderr.rfind('{')
    end = stderr.rfind('}')
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(stderr[start:end + 1])
    except json.JSONDecodeError:
        return None


def normalize_clip_audio(clip_path: str, output_path: str) -> bool:
    """两遍 loudnorm 音量均衡，目标 -16 LUFS / -1.5 dBTP。
    第一遍分析测量值，第二遍以 linear=true 精确均衡，保持视频流不重新编码。
    均衡失败时回退到原始片段。
    """
    stats = analyze_loudness(clip_path)
    if stats is None:
        print(f"    [警告] 响度分析失败，跳过均衡")
        shutil.copy(clip_path, output_path)
        return True

    af = (
        'loudnorm=I=-16:TP=-1.5:LRA=11'
        f':measured_I={stats.get("input_i", "-70")}'
        f':measured_TP={stats.get("input_tp", "-70")}'
        f':measured_LRA={stats.get("input_lra", "0")}'
        f':measured_thresh={stats.get("input_thresh", "-70")}'
        f':offset={stats.get("target_offset", "0")}'
        ':linear=true:print_format=none'
    )
    cmd = [
        'ffmpeg', '-y', '-i', clip_path,
        '-af', af,
        '-c:v', 'copy',
        '-c:a', 'aac', '-b:a', '192k',
        '-avoid_negative_ts', 'make_zero',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"    [警告] 均衡失败，使用原始音频:\n{result.stderr[-200:]}")
        shutil.copy(clip_path, output_path)
    return True


def merge_clips_with_transition(clip_paths: list[str], transition: str,
                                 transition_duration: float, output_path: str) -> bool:
    """使用 xfade filter 添加转场效果拼接片段。"""
    if len(clip_paths) == 1:
        shutil.copy(clip_paths[0], output_path)
        return True

    # 获取每段时长
    durations = []
    for cp in clip_paths:
        d = get_video_duration(cp)
        durations.append(d)

    # 构建 xfade filter_complex
    # 参考：https://trac.ffmpeg.org/wiki/Xfade
    inputs = ' '.join(f'-i {cp}' for cp in clip_paths)

    n = len(clip_paths)
    filter_parts = []
    # 视频流 xfade 链
    offset = durations[0] - transition_duration
    prev_v = '[0:v]'
    prev_a = '[0:a]'

    for i in range(1, n):
        out_v = f'[v{i}]' if i < n - 1 else '[vout]'
        out_a = f'[a{i}]' if i < n - 1 else '[aout]'
        filter_parts.append(
            f"{prev_v}[{i}:v]xfade=transition={transition}:"
            f"duration={transition_duration}:offset={offset:.3f}{out_v}"
        )
        filter_parts.append(
            f"{prev_a}[{i}:a]acrossfade=d={transition_duration}{out_a}"
        )
        offset += durations[i] - transition_duration
        prev_v = out_v
        prev_a = out_a

    filter_complex = '; '.join(filter_parts)

    cmd = ['ffmpeg', '-y']
    for cp in clip_paths:
        cmd += ['-i', cp]
    cmd += [
        '-filter_complex', filter_complex,
        '-map', '[vout]', '-map', '[aout]',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'aac', '-b:a', '192k',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [错误] 转场合并失败，尝试无转场模式:\n{result.stderr[-300:]}")
        return merge_clips_simple(clip_paths, output_path)
    return True


def format_duration(seconds: float) -> str:
    """格式化秒数为 mm:ss 字符串。"""
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m:02d}:{s:02d}"


def main():
    parser = argparse.ArgumentParser(description='根据 clips JSON 使用 FFmpeg 剪辑合并视频')
    parser.add_argument('--clips-json', required=True, help='clips JSON 文件路径（或 JSON 字符串）')
    parser.add_argument('--output', help='覆盖 JSON 中的输出路径')
    args = parser.parse_args()

    if not check_ffmpeg():
        print("[错误] 未找到 FFmpeg，请先安装：brew install ffmpeg")
        sys.exit(1)

    # 读取 clips JSON
    clips_json_path = Path(args.clips_json)
    if clips_json_path.exists():
        config = json.loads(clips_json_path.read_text(encoding='utf-8'))
    else:
        config = json.loads(args.clips_json)

    clips = config.get('clips', [])
    transition = config.get('transition', 'none')
    transition_duration = float(config.get('transition_duration', 1.0))
    normalize_audio = config.get('normalize_audio', True)
    # 兼容 'output' 和 'output_path' 两种写法
    output_path = args.output or config.get('output_path') or config.get('output', '/tmp/output_cut.mp4')

    if transition not in SUPPORTED_TRANSITIONS:
        print(f"[警告] 不支持的转场 '{transition}'，使用 'none'")
        transition = 'none'

    if not clips:
        print("[错误] clips 列表为空")
        sys.exit(1)

    print(f"\n{'='*50}")
    print(f"准备剪辑 {len(clips)} 个片段，转场效果：{transition}")
    print(f"{'='*50}")

    # 创建临时目录存放中间片段
    with tempfile.TemporaryDirectory() as tmpdir:
        clip_files = []
        total_duration = 0.0

        for i, clip in enumerate(clips):
            # 兼容 'file' 和 'video_file' 两种写法
            video_file = clip.get('video_file') or clip.get('file', '')
            start = float(clip.get('start', 0))
            end = float(clip.get('end', 0))
            reason = clip.get('reason', '')

            if not Path(video_file).exists():
                print(f"  [警告] 视频文件不存在: {video_file}，跳过")
                continue

            clip_path = os.path.join(tmpdir, f'clip_{i:03d}.mp4')
            print(f"\n[{i+1}/{len(clips)}] 截取 {format_duration(start)} - {format_duration(end)}")
            print(f"  视频: {Path(video_file).name}")
            if reason:
                print(f"  原因: {reason}")

            video_duration = get_video_duration(video_file)
            success = extract_clip(video_file, start, end, clip_path, video_duration)
            if success:
                clip_files.append(clip_path)
                total_duration += (end - start)
                print(f"  ✓ 片段时长: {format_duration(end - start)}")

        if not clip_files:
            print("\n[错误] 没有成功截取到任何片段")
            sys.exit(1)

        # 音量均衡（多片段时默认开启，避免不同来源视频音量差异）
        if normalize_audio and len(clip_files) > 1:
            print(f"\n{'='*50}")
            print(f"音量均衡（EBU R128 loudnorm，目标 -16 LUFS）")
            norm_files = []
            for i, cp in enumerate(clip_files):
                norm_path = os.path.join(tmpdir, f'clip_{i:03d}_norm.mp4')
                print(f"  [{i+1}/{len(clip_files)}] {Path(cp).name}", end=' ... ', flush=True)
                normalize_clip_audio(cp, norm_path)
                norm_files.append(norm_path)
                print('✓')
            clip_files = norm_files

        # 分辨率归一化（多片段且分辨率不一致时，计算最优分辨率并补黑边）
        if len(clip_files) > 1:
            resolutions = [get_video_resolution(cp) for cp in clip_files]
            unique_res = set(resolutions)
            if len(unique_res) > 1:
                target_w, target_h = compute_optimal_resolution(resolutions)
                print(f"\n{'='*50}")
                print(f"分辨率归一化 → 最优目标: {target_w}x{target_h}")
                print(f"  检测到 {len(unique_res)} 种分辨率: "
                      f"{', '.join(f'{w}x{h}' for w, h in sorted(unique_res))}")
                res_files = []
                for i, cp in enumerate(clip_files):
                    res_path = os.path.join(tmpdir, f'clip_{i:03d}_res.mp4')
                    w, h = resolutions[i]
                    if (w, h) == (target_w, target_h):
                        print(f"  [{i+1}/{len(clip_files)}] {w}x{h} → 已匹配，跳过")
                        shutil.copy(cp, res_path)
                    else:
                        print(f"  [{i+1}/{len(clip_files)}] {w}x{h} → {target_w}x{target_h}（补黑边）")
                        normalize_clip_resolution(cp, res_path, target_w, target_h)
                    res_files.append(res_path)
                clip_files = res_files

        print(f"\n{'='*50}")
        print(f"合并 {len(clip_files)} 个片段 → {output_path}")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        if transition == 'none' or len(clip_files) == 1:
            success = merge_clips_simple(clip_files, output_path)
        else:
            success = merge_clips_with_transition(clip_files, transition, transition_duration, output_path)

        if success:
            actual_duration = get_video_duration(output_path)
            print(f"\n✅ 剪辑完成！")
            print(f"   输出文件: {output_path}")
            print(f"   总时长: {format_duration(actual_duration)}")
            print(f"   截取片段数: {len(clip_files)}")
        else:
            print("\n[错误] 合并失败")
            sys.exit(1)


if __name__ == '__main__':
    main()
