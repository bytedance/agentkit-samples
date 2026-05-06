#!/usr/bin/env python3
# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
FFmpeg Media Tool - 本地音视频处理工具
基于 FFmpeg，21 项能力，零云依赖。
"""

import argparse
import os
import platform
import shutil
import stat
import ssl
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import urllib.parse

# ─── FFmpeg 检测与安装 ───

FFMPEG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".ffmpeg_bin")


def _find_bin(name):
    """查找可用的 ffmpeg/ffprobe 二进制"""
    # 1. 优先系统 PATH
    p = shutil.which(name)
    if p:
        return p
    # 2. 本地下载目录
    local = os.path.join(FFMPEG_DIR, name)
    if os.path.isfile(local) and os.access(local, os.X_OK):
        return local
    return None


def _download_ffmpeg():
    """下载静态编译的 ffmpeg（仅 Linux x86_64）"""
    if platform.system() != "Linux" or platform.machine() not in ("x86_64", "AMD64"):
        print("ERROR: 自动下载仅支持 Linux x86_64，请手动安装 ffmpeg", file=sys.stderr)
        sys.exit(1)
    os.makedirs(FFMPEG_DIR, exist_ok=True)
    url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
    tar_path = os.path.join(FFMPEG_DIR, "ffmpeg.tar.xz")
    print(f"正在下载 FFmpeg 静态版本...\n  {url}")
    try:
        urllib.request.urlretrieve(url, tar_path)
    except Exception as e:
        print(f"ERROR: 下载失败: {e}", file=sys.stderr)
        sys.exit(1)
    print("正在解压...")
    with tarfile.open(tar_path, "r:xz") as tf:
        for member in tf.getmembers():
            basename = os.path.basename(member.name)
            if basename in ("ffmpeg", "ffprobe"):
                member.name = basename
                tf.extract(member, FFMPEG_DIR)
                fpath = os.path.join(FFMPEG_DIR, basename)
                os.chmod(fpath, os.stat(fpath).st_mode | stat.S_IEXEC)
    os.remove(tar_path)
    print("FFmpeg 安装完成")


def get_ffmpeg():
    ff = _find_bin("ffmpeg")
    if not ff:
        _download_ffmpeg()
        ff = _find_bin("ffmpeg")
    if not ff:
        print("ERROR: 无法找到或安装 ffmpeg", file=sys.stderr)
        sys.exit(1)
    return ff


def get_ffprobe():
    fp = _find_bin("ffprobe")
    if not fp:
        _download_ffmpeg()
        fp = _find_bin("ffprobe")
    if not fp:
        print("ERROR: 无法找到或安装 ffprobe", file=sys.stderr)
        sys.exit(1)
    return fp


def run_cmd(cmd, desc=""):
    """执行命令并打印结果"""
    print(f">>> {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR [{desc}]: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    if result.stdout.strip():
        print(result.stdout.strip())
    return result


def get_duration(ffprobe, path):
    """获取媒体时长（秒）"""
    r = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        capture_output=True,
        text=True,
    )
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def resolve_output(output, default, work_dir=None):
    """解析输出路径，默认写到工作目录"""
    if output:
        return os.path.abspath(output)
    wd = work_dir or os.getcwd()
    return os.path.join(wd, default)


# ─── URL 下载支持 ───

_temp_dir = None  # 延迟创建的临时目录


def _is_url(path):
    return path.startswith("http://") or path.startswith("https://")


def _url_to_local(url):
    """将在线 URL 下载到本地临时文件，返回本地路径"""
    global _temp_dir
    if _temp_dir is None:
        _temp_dir = tempfile.mkdtemp(prefix="ffmpeg_tool_")
    # 从 URL 中提取文件名
    parsed = urllib.parse.urlparse(url)
    basename = os.path.basename(parsed.path) or "download"
    # 去除查询参数中的特殊字符，保留文件名
    if not os.path.splitext(basename)[1]:
        basename += ".mp4"  # 无后缀时默认 mp4
    local_path = os.path.join(_temp_dir, basename)
    # 避免重名覆盖
    counter = 1
    base, ext = os.path.splitext(local_path)
    while os.path.exists(local_path):
        local_path = f"{base}_{counter}{ext}"
        counter += 1
    print(f"⬇ 下载: {url}")
    try:
        urllib.request.urlretrieve(url, local_path)
    except urllib.error.URLError:
        # SSL 证书验证失败时降级为不验证
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
        with opener.open(url) as resp, open(local_path, "wb") as f:
            shutil.copyfileobj(resp, f)
    print(f"  → {local_path}")
    return local_path


def _cleanup_temp():
    """清理临时下载文件"""
    global _temp_dir
    if _temp_dir and os.path.isdir(_temp_dir):
        shutil.rmtree(_temp_dir, ignore_errors=True)
        _temp_dir = None


def _resolve_inputs(args):
    """预处理所有输入参数，将 URL 下载为本地文件"""
    # 处理 -i/--input（列表）
    if hasattr(args, "input") and args.input:
        args.input = [_url_to_local(p) if _is_url(p) else p for p in args.input]
    # 处理 --audio
    if hasattr(args, "audio") and args.audio and _is_url(args.audio):
        args.audio = _url_to_local(args.audio)
    # 处理 --subtitle
    if hasattr(args, "subtitle") and args.subtitle and _is_url(args.subtitle):
        args.subtitle = _url_to_local(args.subtitle)
    # 处理 --image
    if hasattr(args, "image") and args.image and _is_url(args.image):
        args.image = _url_to_local(args.image)


# ═══════════════════════════════════════════
# 命令实现
# ═══════════════════════════════════════════


# ─── 1. concat-video ───
def cmd_concat_video(args):
    ff = get_ffmpeg()
    inputs = args.input
    if len(inputs) < 2:
        print("ERROR: 至少需要 2 个输入视频", file=sys.stderr)
        sys.exit(1)
    out = resolve_output(args.output, "concat_output.mp4")

    if args.transition:
        # xfade + acrossfade 转场拼接
        durations = [get_duration(get_ffprobe(), f) for f in inputs]
        td = args.transition_duration
        n = len(inputs)
        filter_parts = []
        # 视频 xfade 链
        prev = "[0:v]"
        for i in range(1, n):
            offset = sum(durations[:i]) - td * i
            if offset < 0:
                offset = 0
            tag = f"[v{i - 1}{i}]" if i < n - 1 else "[outv]"
            filter_parts.append(
                f"{prev}[{i}:v]xfade=transition={args.transition}:duration={td}:offset={offset}{tag}"
            )
            prev = tag
        # 音频 acrossfade 链
        prev_a = "[0:a]"
        for i in range(1, n):
            tag_a = f"[a{i - 1}{i}]" if i < n - 1 else "[outa]"
            filter_parts.append(f"{prev_a}[{i}:a]acrossfade=d={td}{tag_a}")
            prev_a = tag_a
        fc = ";".join(filter_parts)
        cmd = [ff, "-y", "-hide_banner"]
        for f in inputs:
            cmd += ["-i", f]
        cmd += [
            "-filter_complex",
            fc,
            "-map",
            "[outv]",
            "-map",
            "[outa]",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-b:v",
            "1500k",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            out,
        ]
    else:
        # concat demuxer 无转场
        filelist = resolve_output(None, ".filelist_video.txt")
        with open(filelist, "w") as f:
            for inp in inputs:
                f.write(f"file '{os.path.abspath(inp)}'\n")
        cmd = [
            ff,
            "-y",
            "-hide_banner",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            filelist,
            "-c",
            "copy",
            out,
        ]

    run_cmd(cmd, "concat-video")
    print(f"\n✅ 输出: {out}")


# ─── 2. concat-audio ───
def cmd_concat_audio(args):
    ff = get_ffmpeg()
    inputs = args.input
    if len(inputs) < 2:
        print("ERROR: 至少需要 2 个输入音频", file=sys.stderr)
        sys.exit(1)
    out = resolve_output(args.output, "concat_audio.m4a")
    filelist = resolve_output(None, ".filelist_audio.txt")
    with open(filelist, "w") as f:
        for inp in inputs:
            f.write(f"file '{os.path.abspath(inp)}'\n")
    cmd = [
        ff,
        "-y",
        "-hide_banner",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        filelist,
        "-c",
        "copy",
        out,
    ]
    run_cmd(cmd, "concat-audio")
    print(f"\n✅ 输出: {out}")


# ─── 3. trim-video ───
def cmd_trim_video(args):
    ff = get_ffmpeg()
    out = resolve_output(args.output, "trimmed_video.mp4")
    cmd = [ff, "-y", "-hide_banner", "-i", args.input[0]]
    if args.start:
        cmd += ["-ss", str(args.start)]
    if args.end:
        cmd += ["-to", str(args.end)]
    cmd += [
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-b:v",
        args.bitrate,
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        out,
    ]
    run_cmd(cmd, "trim-video")
    print(f"\n✅ 输出: {out}")


# ─── 4. trim-audio ───
def cmd_trim_audio(args):
    ff = get_ffmpeg()
    out = resolve_output(args.output, "trimmed_audio.mp3")
    cmd = [ff, "-y", "-hide_banner", "-i", args.input[0]]
    if args.start:
        cmd += ["-ss", str(args.start)]
    if args.end:
        cmd += ["-to", str(args.end)]
    cmd += ["-map", "0:a:0", "-c:a", "libmp3lame", "-b:a", args.bitrate, out]
    run_cmd(cmd, "trim-audio")
    print(f"\n✅ 输出: {out}")


# ─── 5. mux-audio-video ───
def cmd_mux_audio_video(args):
    ff = get_ffmpeg()
    out = resolve_output(args.output, "muxed.mp4")
    if args.mode == "mix":
        cmd = [
            ff,
            "-y",
            "-hide_banner",
            "-i",
            args.input[0],
            "-i",
            args.audio,
            "-filter_complex",
            "[0:a][1:a]amix=inputs=2:duration=shortest:dropout_transition=1[outa]",
            "-map",
            "0:v:0",
            "-map",
            "[outa]",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-b:v",
            args.bitrate,
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            out,
        ]
    else:  # replace
        cmd = [
            ff,
            "-y",
            "-hide_banner",
            "-i",
            args.input[0],
            "-i",
            args.audio,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-shortest",
            out,
        ]
    run_cmd(cmd, "mux-audio-video")
    print(f"\n✅ 输出: {out}")


# ─── 6. extract-audio ───

_AUDIO_CODEC_EXT = {
    "aac": "m4a",
    "mp3": "mp3",
    "flac": "flac",
    "vorbis": "ogg",
    "opus": "ogg",
    "pcm_s16le": "wav",
    "pcm_s24le": "wav",
}
_FORMAT_ENCODER = {
    "m4a": ("aac", "192k"),
    "mp3": ("libmp3lame", "192k"),
    "flac": ("flac", None),
    "wav": ("pcm_s16le", None),
    "ogg": ("libvorbis", "192k"),
}


def _get_audio_codec(path):
    fp = get_ffprobe()
    r = subprocess.run(
        [
            fp,
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_name",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        capture_output=True,
        text=True,
    )
    return r.stdout.strip()


def cmd_extract_audio(args):
    ff = get_ffmpeg()
    src = args.input[0]
    fmt = args.format

    if fmt:
        encoder, bitrate = _FORMAT_ENCODER[fmt]
        out = resolve_output(args.output, f"extracted_audio.{fmt}")
        cmd = [ff, "-y", "-hide_banner", "-i", src, "-map", "0:a:0", "-c:a", encoder]
        if bitrate:
            cmd += ["-b:a", bitrate]
        cmd.append(out)
    else:
        src_codec = _get_audio_codec(src)
        ext = _AUDIO_CODEC_EXT.get(src_codec, "m4a")
        out = resolve_output(args.output, f"extracted_audio.{ext}")
        if src_codec in _AUDIO_CODEC_EXT:
            cmd = [
                ff,
                "-y",
                "-hide_banner",
                "-i",
                src,
                "-map",
                "0:a:0",
                "-c:a",
                "copy",
                out,
            ]
        else:
            cmd = [
                ff,
                "-y",
                "-hide_banner",
                "-i",
                src,
                "-map",
                "0:a:0",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                out,
            ]

    run_cmd(cmd, "extract-audio")
    print(f"\n✅ 输出: {out}")


# ─── 7. flip-video ───
def cmd_flip_video(args):
    ff = get_ffmpeg()
    out = resolve_output(args.output, "flipped.mp4")
    d = args.direction
    if d == "horizontal":
        vf = "hflip"
    elif d == "vertical":
        vf = "vflip"
    else:
        vf = "hflip,vflip"
    cmd = [
        ff,
        "-y",
        "-hide_banner",
        "-i",
        args.input[0],
        "-filter_complex",
        f"[0:v]{vf}[outv]",
        "-map",
        "[outv]",
        "-map",
        "0:a:0?",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-b:v",
        "1200k",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        out,
    ]
    run_cmd(cmd, "flip-video")
    print(f"\n✅ 输出: {out}")


# ─── 8. adjust-speed ───
def cmd_adjust_speed(args):
    ff = get_ffmpeg()
    out = resolve_output(args.output, "speed_adjusted.mp4")
    speed = args.speed
    vf = f"setpts={1.0 / speed}*PTS"
    # atempo 范围 0.5~100，超出需级联
    atempo_parts = []
    s = speed
    while s > 100.0:
        atempo_parts.append("atempo=100.0")
        s /= 100.0
    while s < 0.5:
        atempo_parts.append("atempo=0.5")
        s /= 0.5
    atempo_parts.append(f"atempo={s}")
    af = ",".join(atempo_parts)
    cmd = [
        ff,
        "-y",
        "-hide_banner",
        "-i",
        args.input[0],
        "-filter_complex",
        f"[0:v]{vf}[outv];[0:a]{af}[outa]",
        "-map",
        "[outv]",
        "-map",
        "[outa]",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-b:v",
        "1200k",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        out,
    ]
    run_cmd(cmd, "adjust-speed")
    print(f"\n✅ 输出: {out}")


# ─── 9. add-subtitle ───
def cmd_add_subtitle(args):
    ff = get_ffmpeg()
    out = resolve_output(args.output, "subtitled.mp4")
    sub_path = os.path.abspath(args.subtitle)
    # 需要转义冒号和反斜杠给 subtitles 滤镜
    sub_escaped = sub_path.replace("\\", "\\\\").replace(":", "\\:")
    style = f"FontSize={args.font_size},Alignment={args.alignment}"
    cmd = [
        ff,
        "-y",
        "-hide_banner",
        "-i",
        args.input[0],
        "-vf",
        f"subtitles=filename={sub_escaped}:force_style='{style}'",
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-b:v",
        "1300k",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        out,
    ]
    run_cmd(cmd, "add-subtitle")
    print(f"\n✅ 输出: {out}")


# ─── 10. add-overlay ───
def cmd_add_overlay(args):
    ff = get_ffmpeg()
    out = resolve_output(args.output, "overlaid.mp4")
    scale_expr = f"scale=iw*{args.scale}:-1"
    # 位置解析
    pos = args.position
    pos_map = {
        "top-left": "10:10",
        "top-right": "W-w-10:10",
        "bottom-left": "10:H-h-10",
        "bottom-right": "W-w-10:H-h-10",
        "center": "(W-w)/2:(H-h)/2",
    }
    overlay_pos = pos_map.get(pos, pos)  # 也支持直接传 x:y
    enable = ""
    if args.start_time is not None and args.end_time is not None:
        enable = f":enable='between(t,{args.start_time},{args.end_time})'"
    elif args.start_time is not None:
        enable = f":enable='gte(t,{args.start_time})'"
    elif args.end_time is not None:
        enable = f":enable='lte(t,{args.end_time})'"
    fc = f"[1:v]{scale_expr}[wm];[0:v][wm]overlay={overlay_pos}{enable}[outv]"
    cmd = [
        ff,
        "-y",
        "-hide_banner",
        "-i",
        args.input[0],
        "-i",
        args.image,
        "-filter_complex",
        fc,
        "-map",
        "[outv]",
        "-map",
        "0:a:0?",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-b:v",
        "1300k",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        out,
    ]
    run_cmd(cmd, "add-overlay")
    print(f"\n✅ 输出: {out}")


# ─── 11. transcode ───
def cmd_transcode(args):
    ff = get_ffmpeg()
    fmt = args.format
    if not fmt and args.output:
        fmt = os.path.splitext(args.output)[1].lstrip(".")
    if not fmt:
        fmt = "mp4"
    out = resolve_output(args.output, f"transcoded.{fmt}")
    codec = args.codec or "copy"
    cmd = [ff, "-y", "-hide_banner", "-i", args.input[0], "-map", "0"]
    if codec == "copy":
        cmd += ["-c", "copy"]
    else:
        cmd += [
            "-c:v",
            codec,
            "-b:v",
            args.bitrate,
            "-c:a",
            args.audio_codec,
            "-b:a",
            args.audio_bitrate,
        ]
    cmd.append(out)
    run_cmd(cmd, "transcode")
    print(f"\n✅ 输出: {out}")


# ─── 12. extract-frames ───
def cmd_extract_frames(args):
    ff = get_ffmpeg()
    out_dir = resolve_output(args.output, "frames")
    os.makedirs(out_dir, exist_ok=True)
    ext = args.format
    pattern = os.path.join(out_dir, f"frame_%03d.{ext}")
    cmd = [
        ff,
        "-y",
        "-hide_banner",
        "-i",
        args.input[0],
        "-vf",
        f"fps={args.fps}",
        "-q:v",
        str(args.quality),
        pattern,
    ]
    run_cmd(cmd, "extract-frames")
    frames = sorted(os.listdir(out_dir))
    print(f"\n✅ 抽帧完成，共 {len(frames)} 帧，输出目录: {out_dir}")


# ─── 13. rotate ───
def cmd_rotate(args):
    ff = get_ffmpeg()
    out = resolve_output(args.output, "rotated.mp4")
    angle_map = {90: "transpose=1", 180: "transpose=1,transpose=1", 270: "transpose=2"}
    vf = angle_map.get(args.angle)
    if not vf:
        print(f"ERROR: 不支持的角度 {args.angle}，仅支持 90/180/270", file=sys.stderr)
        sys.exit(1)
    cmd = [
        ff,
        "-y",
        "-hide_banner",
        "-i",
        args.input[0],
        "-vf",
        vf,
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-b:v",
        "1200k",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        out,
    ]
    run_cmd(cmd, "rotate")
    print(f"\n✅ 输出: {out}")


# ─── 14. resize ───
def cmd_resize(args):
    ff = get_ffmpeg()
    out = resolve_output(args.output, "resized.mp4")
    presets = {"720p": "1280:720", "1080p": "1920:1080", "4k": "3840:2160"}
    if args.preset:
        scale = presets.get(args.preset)
        if not scale:
            print(f"ERROR: 不支持的预设 {args.preset}", file=sys.stderr)
            sys.exit(1)
    else:
        w = args.width or -1
        h = args.height or -1
        scale = f"{w}:{h}"
    cmd = [
        ff,
        "-y",
        "-hide_banner",
        "-i",
        args.input[0],
        "-vf",
        f"scale={scale}:force_original_aspect_ratio=decrease,pad={scale.split(':')[0] if ':' in scale else scale}:{scale.split(':')[1] if ':' in scale else scale}:(ow-iw)/2:(oh-ih)/2,setsar=1",
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-b:v",
        "1500k",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        out,
    ]
    run_cmd(cmd, "resize")
    print(f"\n✅ 输出: {out}")


# ─── 15. crop ───
def cmd_crop(args):
    ff = get_ffmpeg()
    out = resolve_output(args.output, "cropped.mp4")
    cmd = [
        ff,
        "-y",
        "-hide_banner",
        "-i",
        args.input[0],
        "-vf",
        f"crop={args.width}:{args.height}:{args.x}:{args.y}",
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-b:v",
        "1200k",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        out,
    ]
    run_cmd(cmd, "crop")
    print(f"\n✅ 输出: {out}")


# ─── 16. volume ───
def cmd_volume(args):
    ff = get_ffmpeg()
    out = resolve_output(args.output, "volume_adjusted.mp4")
    cmd = [
        ff,
        "-y",
        "-hide_banner",
        "-i",
        args.input[0],
        "-af",
        f"volume={args.level}",
        "-map",
        "0:v:0?",
        "-map",
        "0:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        out,
    ]
    run_cmd(cmd, "volume")
    print(f"\n✅ 输出: {out}")


# ─── 17. audio-fade ───
def cmd_audio_fade(args):
    ff = get_ffmpeg()
    out = resolve_output(args.output, "faded.mp4")
    filters = []
    if args.fade_in and args.fade_in > 0:
        filters.append(f"afade=t=in:st=0:d={args.fade_in}")
    if args.fade_out and args.fade_out > 0:
        dur = get_duration(get_ffprobe(), args.input[0])
        st = max(0, dur - args.fade_out)
        filters.append(f"afade=t=out:st={st}:d={args.fade_out}")
    af = ",".join(filters) if filters else "anull"
    cmd = [
        ff,
        "-y",
        "-hide_banner",
        "-i",
        args.input[0],
        "-af",
        af,
        "-map",
        "0:v:0?",
        "-map",
        "0:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        out,
    ]
    run_cmd(cmd, "audio-fade")
    print(f"\n✅ 输出: {out}")


# ─── 18. to-gif ───
def cmd_to_gif(args):
    ff = get_ffmpeg()
    out = resolve_output(args.output, "output.gif")
    palette = resolve_output(None, ".palette.png")
    base_filter = f"fps={args.fps},scale={args.width}:-1:flags=lanczos"
    time_args = []
    if args.start:
        time_args += ["-ss", str(args.start)]
    if args.end:
        time_args += ["-to", str(args.end)]
    # 第一步：生成调色板
    cmd1 = (
        [ff, "-y", "-hide_banner"]
        + time_args
        + [
            "-i",
            args.input[0],
            "-vf",
            f"{base_filter},palettegen=stats_mode=diff",
            palette,
        ]
    )
    run_cmd(cmd1, "to-gif (palette)")
    # 第二步：用调色板生成 GIF
    cmd2 = (
        [ff, "-y", "-hide_banner"]
        + time_args
        + [
            "-i",
            args.input[0],
            "-i",
            palette,
            "-lavfi",
            f"{base_filter}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5",
            out,
        ]
    )
    run_cmd(cmd2, "to-gif (render)")
    if os.path.exists(palette):
        os.remove(palette)
    print(f"\n✅ 输出: {out}")


# ─── 19. screenshot ───
def cmd_screenshot(args):
    ff = get_ffmpeg()
    out = resolve_output(args.output, "screenshot.jpg")
    cmd = [
        ff,
        "-y",
        "-hide_banner",
        "-ss",
        str(args.time),
        "-i",
        args.input[0],
        "-frames:v",
        "1",
        "-q:v",
        str(args.quality),
        out,
    ]
    run_cmd(cmd, "screenshot")
    print(f"\n✅ 输出: {out}")


# ─── 20. probe ───
def cmd_probe(args):
    fp = get_ffprobe()
    if args.format == "json":
        cmd = [
            fp,
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-print_format",
            "json",
            args.input[0],
        ]
    else:
        cmd = [fp, "-v", "error", "-show_format", "-show_streams", args.input[0]]
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)


# ─── 21. replace-audio ───
def cmd_replace_audio(args):
    ff = get_ffmpeg()
    out = resolve_output(args.output, "replaced_audio.mp4")
    cmd = [
        ff,
        "-y",
        "-hide_banner",
        "-i",
        args.input[0],
        "-i",
        args.audio,
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-shortest",
        out,
    ]
    run_cmd(cmd, "replace-audio")
    print(f"\n✅ 输出: {out}")


# ═══════════════════════════════════════════
# CLI 解析
# ═══════════════════════════════════════════


def build_parser():
    parser = argparse.ArgumentParser(
        prog="ffmpeg_tool",
        description="FFmpeg Media Tool - 本地音视频处理（21 项能力）",
    )
    sub = parser.add_subparsers(dest="command", help="子命令")

    # --- concat-video ---
    p = sub.add_parser("concat-video", help="视频拼接")
    p.add_argument("-i", "--input", action="append", required=True)
    p.add_argument("-o", "--output")
    p.add_argument("--transition")
    p.add_argument("--transition-duration", type=float, default=1.0)
    p.set_defaults(func=cmd_concat_video)

    # --- concat-audio ---
    p = sub.add_parser("concat-audio", help="音频拼接")
    p.add_argument("-i", "--input", action="append", required=True)
    p.add_argument("-o", "--output")
    p.set_defaults(func=cmd_concat_audio)

    # --- trim-video ---
    p = sub.add_parser("trim-video", help="视频裁剪")
    p.add_argument("-i", "--input", action="append", required=True)
    p.add_argument("-o", "--output")
    p.add_argument("--start", "-ss")
    p.add_argument("--end", "-to")
    p.add_argument("--bitrate", default="1200k")
    p.set_defaults(func=cmd_trim_video)

    # --- trim-audio ---
    p = sub.add_parser("trim-audio", help="音频裁剪")
    p.add_argument("-i", "--input", action="append", required=True)
    p.add_argument("-o", "--output")
    p.add_argument("--start")
    p.add_argument("--end")
    p.add_argument("--bitrate", default="192k")
    p.set_defaults(func=cmd_trim_audio)

    # --- mux-audio-video ---
    p = sub.add_parser("mux-audio-video", help="音视频合成/混音")
    p.add_argument("-i", "--input", action="append", required=True)
    p.add_argument("--audio", required=True)
    p.add_argument("-o", "--output")
    p.add_argument("--mode", default="mix", choices=["mix", "replace"])
    p.add_argument("--bitrate", default="1200k")
    p.set_defaults(func=cmd_mux_audio_video)

    # --- extract-audio ---
    p = sub.add_parser("extract-audio", help="提取音频")
    p.add_argument("-i", "--input", action="append", required=True)
    p.add_argument("-o", "--output")
    p.add_argument(
        "--format",
        choices=["m4a", "mp3", "flac", "wav", "ogg"],
        help="输出格式（默认自动检测源编码）",
    )
    p.set_defaults(func=cmd_extract_audio)

    # --- flip-video ---
    p = sub.add_parser("flip-video", help="视频翻转")
    p.add_argument("-i", "--input", action="append", required=True)
    p.add_argument("-o", "--output")
    p.add_argument(
        "--direction", default="horizontal", choices=["horizontal", "vertical", "both"]
    )
    p.set_defaults(func=cmd_flip_video)

    # --- adjust-speed ---
    p = sub.add_parser("adjust-speed", help="视频调速")
    p.add_argument("-i", "--input", action="append", required=True)
    p.add_argument("-o", "--output")
    p.add_argument("--speed", type=float, required=True)
    p.set_defaults(func=cmd_adjust_speed)

    # --- add-subtitle ---
    p = sub.add_parser("add-subtitle", help="视频加字幕")
    p.add_argument("-i", "--input", action="append", required=True)
    p.add_argument("--subtitle", required=True)
    p.add_argument("-o", "--output")
    p.add_argument("--font-size", type=int, default=32)
    p.add_argument("--alignment", type=int, default=2)
    p.set_defaults(func=cmd_add_subtitle)

    # --- add-overlay ---
    p = sub.add_parser("add-overlay", help="视频加图片/水印")
    p.add_argument("-i", "--input", action="append", required=True)
    p.add_argument("--image", required=True)
    p.add_argument("-o", "--output")
    p.add_argument("--position", default="bottom-right")
    p.add_argument("--scale", type=float, default=0.15)
    p.add_argument("--start-time", type=float)
    p.add_argument("--end-time", type=float)
    p.set_defaults(func=cmd_add_overlay)

    # --- transcode ---
    p = sub.add_parser("transcode", help="视频转码/转封装")
    p.add_argument("-i", "--input", action="append", required=True)
    p.add_argument("-o", "--output")
    p.add_argument("--format")
    p.add_argument("--codec")
    p.add_argument("--bitrate", default="1500k")
    p.add_argument("--audio-codec", default="aac")
    p.add_argument("--audio-bitrate", default="128k")
    p.set_defaults(func=cmd_transcode)

    # --- extract-frames ---
    p = sub.add_parser("extract-frames", help="视频抽帧")
    p.add_argument("-i", "--input", action="append", required=True)
    p.add_argument("-o", "--output")
    p.add_argument("--fps", type=float, default=1)
    p.add_argument("--quality", type=int, default=3)
    p.add_argument("--format", default="jpg", choices=["jpg", "png"])
    p.set_defaults(func=cmd_extract_frames)

    # --- rotate ---
    p = sub.add_parser("rotate", help="视频旋转")
    p.add_argument("-i", "--input", action="append", required=True)
    p.add_argument("-o", "--output")
    p.add_argument("--angle", type=int, required=True, choices=[90, 180, 270])
    p.set_defaults(func=cmd_rotate)

    # --- resize ---
    p = sub.add_parser("resize", help="分辨率缩放")
    p.add_argument("-i", "--input", action="append", required=True)
    p.add_argument("-o", "--output")
    p.add_argument("--width", type=int)
    p.add_argument("--height", type=int)
    p.add_argument("--preset", choices=["720p", "1080p", "4k"])
    p.set_defaults(func=cmd_resize)

    # --- crop ---
    p = sub.add_parser("crop", help="画面裁切")
    p.add_argument("-i", "--input", action="append", required=True)
    p.add_argument("-o", "--output")
    p.add_argument("--width", type=int, required=True)
    p.add_argument("--height", type=int, required=True)
    p.add_argument("--x", type=int, default=0)
    p.add_argument("--y", type=int, default=0)
    p.set_defaults(func=cmd_crop)

    # --- volume ---
    p = sub.add_parser("volume", help="音量调整")
    p.add_argument("-i", "--input", action="append", required=True)
    p.add_argument("-o", "--output")
    p.add_argument("--level", required=True)
    p.set_defaults(func=cmd_volume)

    # --- audio-fade ---
    p = sub.add_parser("audio-fade", help="音频淡入淡出")
    p.add_argument("-i", "--input", action="append", required=True)
    p.add_argument("-o", "--output")
    p.add_argument("--fade-in", type=float, default=0)
    p.add_argument("--fade-out", type=float, default=0)
    p.set_defaults(func=cmd_audio_fade)

    # --- to-gif ---
    p = sub.add_parser("to-gif", help="GIF 生成")
    p.add_argument("-i", "--input", action="append", required=True)
    p.add_argument("-o", "--output")
    p.add_argument("--start", type=float, default=0)
    p.add_argument("--end", type=float, default=5)
    p.add_argument("--width", type=int, default=480)
    p.add_argument("--fps", type=int, default=10)
    p.set_defaults(func=cmd_to_gif)

    # --- screenshot ---
    p = sub.add_parser("screenshot", help="视频截图")
    p.add_argument("-i", "--input", action="append", required=True)
    p.add_argument("-o", "--output")
    p.add_argument("--time", type=float, default=0)
    p.add_argument("--quality", type=int, default=2)
    p.set_defaults(func=cmd_screenshot)

    # --- probe ---
    p = sub.add_parser("probe", help="元数据读取")
    p.add_argument("-i", "--input", action="append", required=True)
    p.add_argument("--format", default="json", choices=["json", "text"])
    p.set_defaults(func=cmd_probe)

    # --- replace-audio ---
    p = sub.add_parser("replace-audio", help="替换音轨")
    p.add_argument("-i", "--input", action="append", required=True)
    p.add_argument("--audio", required=True)
    p.add_argument("-o", "--output")
    p.set_defaults(func=cmd_replace_audio)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    try:
        _resolve_inputs(args)
        args.func(args)
    finally:
        _cleanup_temp()


if __name__ == "__main__":
    main()
