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

from __future__ import annotations

import os
import sys
import asyncio
import argparse
import json
import subprocess
from typing import Any
from importlib.util import find_spec


LOCAL_FALLBACK_COMMANDS = {
    "trim_media_duration",
    "concat_media_segments",
    "extract_audio",
    "mux_audio_video",
}

CLOUD_ONLY_COMMANDS = {
    "enhance_video",
    "image_to_video",
    "query_task",
    "understand_video_content",
}

LOCAL_ONLY_COMMANDS = {
    "adjust-speed",
    "add-overlay",
    "add-subtitle",
    "flip-video",
    "transcode",
}

LOCAL_ONLY_COMMAND_ALIASES = {
    command.replace("-", "_"): command for command in LOCAL_ONLY_COMMANDS
}
LOCAL_ONLY_COMMAND_ALIASES.update({command: command for command in LOCAL_ONLY_COMMANDS})
PUBLIC_COMMANDS = (
    LOCAL_FALLBACK_COMMANDS | CLOUD_ONLY_COMMANDS | set(LOCAL_ONLY_COMMAND_ALIASES)
)


def _current_command() -> str | None:
    for arg in sys.argv[1:]:
        if arg in ("-h", "--help", "--no-wait"):
            continue
        if arg.startswith("-"):
            continue
        return arg
    return None


def _load_dotenv_if_available(root_dir: str) -> None:
    if find_spec("dotenv"):
        from dotenv import load_dotenv

        load_dotenv(os.path.join(root_dir, ".env"), override=False)


def _cloud_requirements_ready(command: str | None) -> tuple[bool, str]:
    required_pkgs = ["httpx", "pydantic", "dotenv"]
    pkg_missing = [p for p in required_pkgs if not find_spec(p)]
    if pkg_missing:
        return False, "missing Python packages: " + ", ".join(pkg_missing)

    amk_api_key = (os.getenv("AMK_API_KEY") or "").strip()
    if not amk_api_key:
        return False, "missing AMK_API_KEY"

    amk_env = (os.getenv("AMK_ENV") or "prod").strip().lower()
    if amk_env != "prod":
        return False, "invalid AMK_ENV"

    if command == "understand_video_content":
        if not (os.getenv("ARK_API_KEY") or "").strip():
            return False, "missing ARK_API_KEY"
        if not (os.getenv("ARK_MODEL_ID") or "").strip():
            return False, "missing ARK_MODEL_ID"

    return True, ""


# 环境检查与初始化（最先执行）
def env_check_and_init():
    # 仅查看帮助信息时，不做环境/依赖检查（保证 -h/--help 可用）
    if any(a in ("-h", "--help") for a in sys.argv[1:]):
        return

    # 获取当前脚本所在目录（scripts目录）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 项目根目录是scripts的上级目录
    root_dir = os.path.dirname(script_dir)
    env_path = os.path.join(root_dir, ".env")

    command = _current_command()
    _load_dotenv_if_available(root_dir)
    if command and command not in PUBLIC_COMMANDS:
        return
    if command in LOCAL_ONLY_COMMAND_ALIASES:
        return

    cloud_ready, _reason = _cloud_requirements_ready(command)

    if command in LOCAL_FALLBACK_COMMANDS and not cloud_ready:
        os.environ["BYTED_AMK_LOCAL_FALLBACK_REASON"] = "cloud backend unavailable"
        return

    # 1. 自动创建.env文件（不存在时）
    if not os.path.exists(env_path):
        default_env_content = """# AMK API Key (云端能力需要；裁剪/拼接/提取/合成可在缺失时自动走本地 FFmpeg)
AMK_API_KEY=
# AMK 环境固定为 prod（线上）
AMK_ENV=prod
# 是否启用 client_token 自动注入（用于幂等，取值 true/false）
AMK_ENABLE_CLIENT_TOKEN=false
# 方舟 密钥（可选，仅使用视频理解功能时必须配置）
ARK_API_KEY=
# 方舟 模型ID（可选，仅使用视频理解功能时必须配置）
ARK_MODEL_ID=
"""
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(default_env_content)
        print(
            f"已自动创建.env模板文件到 {env_path}，如需使用视频理解功能请配置ARK_API_KEY和ARK_MODEL_ID",
            file=sys.stderr,
        )

    # 2. 检查依赖安装（避免在依赖缺失时顶层 import 直接失败）
    required_pkgs = ["httpx", "pydantic", "dotenv"]
    pkg_missing = [p for p in required_pkgs if not find_spec(p)]
    if pkg_missing:
        raise RuntimeError(
            "依赖缺失，请在 <SKILL_DIR>/scripts 目录创建虚拟环境并安装："
            "python3 -m venv .venv && . .venv/bin/activate && python -m pip install -U pip && python -m pip install -r requirements.txt"
        )

    # 3. 加载环境变量（优先系统环境变量，覆盖.env配置）
    from dotenv import load_dotenv

    load_dotenv(env_path, override=False)

    # 4. 检查必填环境变量
    required_vars = ["AMK_API_KEY", "AMK_ENV"]
    missing = [
        v for v in required_vars if not os.getenv(v) or os.getenv(v).strip() == ""
    ]
    if missing:
        raise RuntimeError(
            f"缺失必填环境变量：{', '.join(missing)}，请在.env文件或ClawAI Skill配置中设置"
        )

    # 5. 校验可选开关变量取值
    client_token_flag = (
        (os.getenv("AMK_ENABLE_CLIENT_TOKEN") or "false").strip().lower()
    )
    if client_token_flag not in ("true", "false"):
        raise RuntimeError("环境变量 AMK_ENABLE_CLIENT_TOKEN 仅支持 true 或 false")


# 立即执行环境检查
try:
    env_check_and_init()
except Exception as e:
    print(f"环境检查失败：{str(e)}", file=sys.stderr)
    sys.exit(1)


# 通用任务轮询函数
async def poll_task_until_complete(client, task_id, timeout=1800):
    """
    轮询任务直到完成或超时
    :param client: AMK客户端实例
    :param task_id: 任务ID
    :param timeout: 超时时间（秒），默认30分钟
    :return: 任务结果
    """
    from amk_client import query_task, normalize_query_task_response

    interval = 2
    total_wait = 0

    while total_wait < timeout:
        resp = await query_task(task_id=task_id)
        resp.raise_for_status()
        task_info = normalize_query_task_response(resp.json())
        status = task_info.status

        if status == "completed":
            return task_info.model_dump()
        if status == "failed":
            return {"status": "failed", "task_id": task_id, "message": "任务执行失败"}
        if status == "canceled":
            return {"status": "canceled", "task_id": task_id, "message": "任务已取消"}

        # 等待下次查询
        await asyncio.sleep(interval)
        total_wait += interval
        interval = min(interval * 1.5, 30)  # 指数退避，最大间隔30秒

    # 超时返回
    return {
        "status": "timeout",
        "task_id": task_id,
        "message": f"任务执行超时，可使用任务ID {task_id} 调用 query_task 手动查询结果",
    }


# 功能处理函数
async def handle_understand_video(client, args):
    """处理视频理解（同步返回）"""
    try:
        from httpx import TimeoutException
        from amk_client import AmkAsyncClient
        from amk_client import understand_video_content

        long_timeout_client = AmkAsyncClient(timeout=600.0)  # 10分钟超时
        result = await understand_video_content(
            prompt=args.prompt,
            video_url=args.video_url,
            fps=args.fps,
            max_frames=args.max_frames,
            client=long_timeout_client,
        )
        return {"status": "success", "result": result}
    except TimeoutException:
        return {
            "status": "timeout",
            "message": "视频理解任务执行超时，请尝试上传更小的视频文件或稍后重试",
        }
    except Exception as e:
        return {
            "status": "failed",
            "message": f"视频理解失败：{str(e)}（请检查是否已配置ARK_API_KEY和ARK_MODEL_ID）",
        }


async def handle_async_task(client, args, task_name):
    """处理异步任务（默认自动轮询返回结果，可通过--no-wait直接返回task_id）"""
    try:
        import httpx
        from amk_client import (
            extract_audio,
            trim_media_duration,
            concat_media_segments,
            mux_audio_video,
            enhance_video,
            image_to_video,
        )

        params = vars(args)
        params.pop("func", None)
        params.pop("command", None)
        no_wait = params.pop("no_wait", False)
        params.pop("output", None)
        params.pop("local_transition", None)
        params.pop("local_transition_duration", None)

        func_map = {
            "extract_audio": extract_audio,
            "trim_media_duration": trim_media_duration,
            "concat_media_segments": concat_media_segments,
            "mux_audio_video": mux_audio_video,
            "enhance_video": enhance_video,
            "image_to_video": image_to_video,
        }

        func = func_map[task_name]
        task = await func(params)

        task_id = None
        submit_response: dict[str, Any] | str | None = None

        if isinstance(task, httpx.Response):
            task.raise_for_status()
            try:
                payload = task.json()
                submit_response = payload
            except ValueError:
                payload = {}
                submit_response = task.text
            print("payload:", payload)
            if isinstance(payload, dict):
                task_id = payload.get("task_id") or payload.get("TaskId")
                if task_id is None and isinstance(payload.get("Result"), dict):
                    task_id = payload["Result"].get("task_id") or payload["Result"].get(
                        "TaskId"
                    )
        elif hasattr(task, "task_id"):
            task_id = getattr(task, "task_id")
            if hasattr(task, "model_dump"):
                submit_response = task.model_dump()
        else:
            submit_response = str(task)

        if not task_id:
            raise ValueError(
                f"提交成功但未返回有效 task_id，submit_response={submit_response}"
            )

        # 如果指定了no_wait，直接返回task_id
        if no_wait:
            return {
                "status": "pending",
                "task_id": task_id,
                "message": "任务已提交，已跳过等待，可调用 query_task 接口传入 task_id 查询结果",
                "query_example": f"./byted-mediakit-tools.sh query_task --task_id {task_id}",
                "submit_response": submit_response,
            }

        # 否则自动轮询等待结果
        return await poll_task_until_complete(client, task_id)
    except Exception as e:
        return {"status": "failed", "message": f"{task_name}任务提交失败：{str(e)}"}


async def handle_query_task(client, args):
    """处理任务查询"""
    try:
        from amk_client import query_task, normalize_query_task_response

        params = vars(args)
        params.pop("func", None)
        resp = await query_task(task_id=params.get("task_id"))
        resp.raise_for_status()
        result = normalize_query_task_response(resp.json())
        return result.model_dump()
    except Exception as e:
        return {"status": "failed", "message": f"任务查询失败：{str(e)}"}


def _is_http_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def _has_local_inputs(args: argparse.Namespace) -> bool:
    if args.command == "trim_media_duration":
        return not _is_http_url(args.source)
    if args.command == "concat_media_segments":
        return any(not _is_http_url(source) for source in args.sources)
    if args.command == "extract_audio":
        return not _is_http_url(args.video_url)
    if args.command == "mux_audio_video":
        return not _is_http_url(args.video_url) or not _is_http_url(args.audio_url)
    return False


def _canonical_local_only_command(command: str) -> str | None:
    return LOCAL_ONLY_COMMAND_ALIASES.get(command)


def _build_local_ffmpeg_args(args: argparse.Namespace) -> list[str]:
    script_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "local_ffmpeg_tool.py"
    )
    cmd = [sys.executable, script_path]
    local_only_command = _canonical_local_only_command(args.command)

    if args.command == "trim_media_duration":
        local_cmd = "trim-audio" if args.type == "audio" else "trim-video"
        cmd.extend([local_cmd, "-i", args.source, "--start", str(args.start_time)])
        if args.end_time is not None:
            cmd.extend(["--end", str(args.end_time)])
        if getattr(args, "output", None):
            cmd.extend(["-o", args.output])
        return cmd

    if args.command == "concat_media_segments":
        local_cmd = "concat-audio" if args.type == "audio" else "concat-video"
        cmd.append(local_cmd)
        for source in args.sources:
            cmd.extend(["-i", source])
        if args.transitions and not getattr(args, "local_transition", None):
            raise ValueError(
                "local fallback does not support cloud transition IDs; "
                "use --local_transition with an FFmpeg xfade transition name for local processing"
            )
        if args.type == "video" and getattr(args, "local_transition", None):
            cmd.extend(["--transition", args.local_transition])
            cmd.extend(["--transition-duration", str(args.local_transition_duration)])
        if getattr(args, "output", None):
            cmd.extend(["-o", args.output])
        return cmd

    if args.command == "extract_audio":
        cmd.extend(["extract-audio", "-i", args.video_url])
        if args.format:
            cmd.extend(["--format", args.format])
        if getattr(args, "output", None):
            cmd.extend(["-o", args.output])
        return cmd

    if args.command == "mux_audio_video":
        if args.is_video_audio_sync:
            raise ValueError(
                "local fallback does not support duration sync for mux_audio_video"
            )
        mode = "mix" if args.is_audio_reserve else "replace"
        cmd.extend(
            [
                "mux-audio-video",
                "-i",
                args.video_url,
                "--audio",
                args.audio_url,
                "--mode",
                mode,
            ]
        )
        if getattr(args, "output", None):
            cmd.extend(["-o", args.output])
        return cmd

    if local_only_command == "flip-video":
        cmd.extend(["flip-video", "-i", args.input, "--direction", args.direction])
        if getattr(args, "output", None):
            cmd.extend(["-o", args.output])
        return cmd

    if local_only_command == "adjust-speed":
        cmd.extend(["adjust-speed", "-i", args.input, "--speed", str(args.speed)])
        if getattr(args, "output", None):
            cmd.extend(["-o", args.output])
        return cmd

    if local_only_command == "add-subtitle":
        cmd.extend(
            [
                "add-subtitle",
                "-i",
                args.input,
                "--subtitle",
                args.subtitle,
                "--font-size",
                str(args.font_size),
                "--alignment",
                str(args.alignment),
            ]
        )
        if getattr(args, "output", None):
            cmd.extend(["-o", args.output])
        return cmd

    if local_only_command == "add-overlay":
        cmd.extend(
            [
                "add-overlay",
                "-i",
                args.input,
                "--image",
                args.image,
                "--position",
                args.position,
                "--scale",
                str(args.scale),
            ]
        )
        if args.start_time is not None:
            cmd.extend(["--start-time", str(args.start_time)])
        if args.end_time is not None:
            cmd.extend(["--end-time", str(args.end_time)])
        if getattr(args, "output", None):
            cmd.extend(["-o", args.output])
        return cmd

    if local_only_command == "transcode":
        cmd.extend(["transcode", "-i", args.input])
        for option in (
            "output",
            "format",
            "codec",
            "bitrate",
            "audio_codec",
            "audio_bitrate",
        ):
            value = getattr(args, option, None)
            if value:
                cmd.extend([f"--{option.replace('_', '-')}", str(value)])
        return cmd

    raise ValueError(f"no local fallback for command: {args.command}")


def _local_fallback_reason(args: argparse.Namespace) -> str | None:
    if _canonical_local_only_command(args.command):
        return "local-only command"
    if args.command in LOCAL_FALLBACK_COMMANDS and _has_local_inputs(args):
        return "local input path requires local backend"
    env_reason = os.getenv("BYTED_AMK_LOCAL_FALLBACK_REASON")
    if env_reason:
        return env_reason
    return None


def run_local_fallback(args: argparse.Namespace) -> dict[str, Any]:
    reason = _local_fallback_reason(args)
    if reason is None:
        raise ValueError("local fallback was requested without a reason")
    try:
        cmd = _build_local_ffmpeg_args(args)
    except ValueError as exc:
        return {
            "status": "failed",
            "backend": "local_ffmpeg",
            "fallback_reason": reason,
            "message": str(exc),
        }
    completed = subprocess.run(cmd, capture_output=True, text=True)
    output = completed.stdout + completed.stderr
    if completed.returncode != 0:
        return {
            "status": "failed",
            "backend": "local_ffmpeg",
            "fallback_reason": reason,
            "message": output.strip(),
        }
    return {
        "status": "success",
        "backend": "local_ffmpeg",
        "fallback_reason": reason,
        "command": args.command,
        "output": output.strip(),
    }


# 主函数
def main():
    parser = argparse.ArgumentParser(description="AMK 音视频处理工具集")
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="异步任务不等待结果，直接返回task_id（仅对异步功能生效）",
    )

    subparsers = parser.add_subparsers(
        dest="command", required=True, help="支持的功能，直接使用功能名称调用即可"
    )

    # 1. 视频理解（同步）
    parser_uv = subparsers.add_parser(
        "understand_video_content",
        help="视频内容理解（同步返回结果，需要配置ARK_API_KEY和ARK_MODEL_ID）",
    )
    parser_uv.add_argument(
        "--video_url", required=True, help="【必填】视频文件URL，支持http://或https://"
    )
    parser_uv.add_argument(
        "--prompt",
        required=True,
        help="【必填】用户提示词，描述对视频理解的具体要求，由宿主agent自动解析用户诉求生成",
    )
    parser_uv.add_argument(
        "--fps",
        type=float,
        required=True,
        help="【必填】抽帧帧率，须大于0，支持整数或浮点数",
    )
    parser_uv.add_argument("--max_frames", type=int, help="【可选】最大抽帧数，须大于0")
    parser_uv.set_defaults(func=handle_understand_video)

    # 2. 任务查询
    parser_qt = subparsers.add_parser("query_task", help="查询异步任务结果")
    parser_qt.add_argument("--task_id", required=True, help="【必填】任务查询ID")
    parser_qt.add_argument("--interval", type=int, help="【可选】轮询间隔，默认5秒")
    parser_qt.add_argument(
        "--max_retries", type=int, help="【可选】最大轮询次数，默认6次"
    )
    parser_qt.set_defaults(func=handle_query_task)

    # 3. 异步任务 - 音视频拼接
    parser_cms = subparsers.add_parser(
        "concat_media_segments", help="拼接多个音视频片段，默认自动等待结果"
    )
    parser_cms.add_argument(
        "--type",
        required=True,
        choices=["audio", "video"],
        help="【必填】拼接类型：audio | video",
    )
    parser_cms.add_argument(
        "--sources",
        nargs="+",
        required=True,
        help="【必填】待拼接资源URL列表，支持http://或https://",
    )
    parser_cms.add_argument(
        "--transitions", nargs="+", help="【可选】视频转场ID列表，音频拼接不支持"
    )
    parser_cms.add_argument("--output", help="【本地回退可选】本地处理时的输出文件路径")
    parser_cms.add_argument(
        "--local_transition",
        help="【本地回退可选】FFmpeg xfade 转场名，如 fade/circleopen/radial",
    )
    parser_cms.add_argument(
        "--local_transition_duration",
        type=float,
        default=1.0,
        help="【本地回退可选】本地转场时长，默认1秒",
    )
    parser_cms.set_defaults(
        func=lambda c, a: handle_async_task(c, a, "concat_media_segments")
    )

    # 4. 异步任务 - 画质增强
    parser_ev = subparsers.add_parser(
        "enhance_video", help="视频画质增强，默认自动等待结果"
    )
    parser_ev.add_argument(
        "--video_url", required=True, help="【必填】输入视频URL，支持http://或https://"
    )
    parser_ev.add_argument(
        "--tool_version",
        choices=["standard", "professional"],
        default="standard",
        help="【可选】工具版本：standard 标准版 | professional 专业版，默认 standard",
    )
    parser_ev.add_argument(
        "--resolution",
        choices=["240p", "360p", "480p", "540p", "720p", "1080p", "2k", "4k"],
        help="【可选】目标分辨率；不传则使用原始分辨率",
    )
    parser_ev.add_argument(
        "--resolution_limit",
        type=int,
        choices=range(64, 2161),
        help="【可选】目标长宽限制，范围[64, 2160]",
    )
    parser_ev.add_argument("--fps", type=float, help="【可选】目标帧率，范围(0, 120]")
    parser_ev.set_defaults(func=lambda c, a: handle_async_task(c, a, "enhance_video"))

    # 5. 异步任务 - 音频提取
    parser_ea = subparsers.add_parser(
        "extract_audio", help="从视频提取音频，默认自动等待结果"
    )
    parser_ea.add_argument(
        "--video_url", required=True, help="【必填】输入视频URL，支持http://或https://"
    )
    parser_ea.add_argument(
        "--format",
        choices=["mp3", "m4a"],
        default="m4a",
        help="【可选】输出格式：mp3 | m4a，默认m4a",
    )
    parser_ea.add_argument("--output", help="【本地回退可选】本地处理时的输出文件路径")
    parser_ea.set_defaults(func=lambda c, a: handle_async_task(c, a, "extract_audio"))

    # 6. 异步任务 - 文生视频（图片转视频）
    parser_itv = subparsers.add_parser(
        "image_to_video", help="图片生成视频，默认自动等待结果"
    )
    parser_itv.add_argument(
        "--images",
        required=True,
        nargs="+",
        help="【必填】待合成图片列表，格式：'image_url=xxx,duration=3,animation_type=zoom_in'，多个图片用空格分隔",
    )
    parser_itv.add_argument("--transitions", nargs="+", help="【可选】视频转场ID列表")
    parser_itv.set_defaults(func=lambda c, a: handle_async_task(c, a, "image_to_video"))

    # 7. 异步任务 - 音视频合成
    parser_mav = subparsers.add_parser(
        "mux_audio_video", help="音视频合成，默认自动等待结果"
    )
    parser_mav.add_argument(
        "--video_url",
        required=True,
        help="【必填】待处理视频URL，支持http://或https://",
    )
    parser_mav.add_argument(
        "--audio_url",
        required=True,
        help="【必填】待处理音频URL，支持http://或https://",
    )
    parser_mav.add_argument(
        "--is_audio_reserve",
        type=lambda x: x.lower() in ("true", "1", "yes"),
        default=True,
        help="【可选】是否保留原视频音频，默认true",
    )
    parser_mav.add_argument(
        "--is_video_audio_sync",
        type=lambda x: x.lower() in ("true", "1", "yes"),
        default=False,
        help="【可选】是否对齐音视频时长，默认false",
    )
    parser_mav.add_argument(
        "--sync_mode",
        choices=["video", "audio"],
        help="【可选】对齐模式：video | audio，is_video_audio_sync=true时生效",
    )
    parser_mav.add_argument(
        "--sync_method",
        choices=["speed", "trim"],
        help="【可选】对齐方式：speed | trim，is_video_audio_sync=true时生效",
    )
    parser_mav.add_argument("--output", help="【本地回退可选】本地处理时的输出文件路径")
    parser_mav.set_defaults(
        func=lambda c, a: handle_async_task(c, a, "mux_audio_video")
    )

    # 8. 异步任务 - 媒体裁剪
    parser_tmd = subparsers.add_parser(
        "trim_media_duration", help="裁剪音视频时长，默认自动等待结果"
    )
    parser_tmd.add_argument(
        "--type",
        required=True,
        choices=["audio", "video"],
        help="【必填】媒体类型：audio | video",
    )
    parser_tmd.add_argument(
        "--source", required=True, help="【必填】待剪切的资源URL，支持http://或https://"
    )
    parser_tmd.add_argument(
        "--start_time",
        type=float,
        default=0,
        help="【可选】裁剪开始时间，默认0，支持两位小数，单位秒",
    )
    parser_tmd.add_argument(
        "--end_time",
        type=float,
        help="【可选】裁剪结束时间，默认片源结尾，支持两位小数，单位秒",
    )
    parser_tmd.add_argument("--output", help="【本地回退可选】本地处理时的输出文件路径")
    parser_tmd.set_defaults(
        func=lambda c, a: handle_async_task(c, a, "trim_media_duration")
    )

    # 9. 本地能力 - 视频翻转
    parser_flip = subparsers.add_parser(
        "flip-video", aliases=["flip_video"], help="本地视频翻转（默认水平镜像）"
    )
    parser_flip.add_argument(
        "-i", "--input", required=True, help="【必填】输入视频文件路径或URL"
    )
    parser_flip.add_argument("-o", "--output", help="【可选】输出文件路径")
    parser_flip.add_argument(
        "--direction",
        default="horizontal",
        choices=["horizontal", "vertical", "both"],
        help="【可选】翻转方向，默认 horizontal",
    )

    # 10. 本地能力 - 视频调速
    parser_speed = subparsers.add_parser(
        "adjust-speed", aliases=["adjust_speed"], help="本地视频调速"
    )
    parser_speed.add_argument(
        "-i", "--input", required=True, help="【必填】输入视频文件路径或URL"
    )
    parser_speed.add_argument("-o", "--output", help="【可选】输出文件路径")
    parser_speed.add_argument(
        "--speed", type=float, required=True, help="【必填】速度倍率，如 0.5 或 2.0"
    )

    # 11. 本地能力 - 视频加字幕
    parser_sub = subparsers.add_parser(
        "add-subtitle", aliases=["add_subtitle"], help="本地视频加硬字幕"
    )
    parser_sub.add_argument(
        "-i", "--input", required=True, help="【必填】输入视频文件路径或URL"
    )
    parser_sub.add_argument(
        "--subtitle", required=True, help="【必填】SRT/ASS 字幕文件路径或URL"
    )
    parser_sub.add_argument("-o", "--output", help="【可选】输出文件路径")
    parser_sub.add_argument(
        "--font-size", type=int, default=32, help="【可选】字幕字号，默认32"
    )
    parser_sub.add_argument(
        "--alignment", type=int, default=2, help="【可选】字幕对齐，默认2（底部居中）"
    )

    # 12. 本地能力 - 视频加水印/叠图
    parser_overlay = subparsers.add_parser(
        "add-overlay", aliases=["add_overlay"], help="本地视频加图片/水印"
    )
    parser_overlay.add_argument(
        "-i", "--input", required=True, help="【必填】输入视频文件路径或URL"
    )
    parser_overlay.add_argument(
        "--image", required=True, help="【必填】水印图片路径或URL"
    )
    parser_overlay.add_argument("-o", "--output", help="【可选】输出文件路径")
    parser_overlay.add_argument(
        "--position",
        default="bottom-right",
        help="【可选】位置：top-left/top-right/bottom-left/bottom-right/center 或 x:y",
    )
    parser_overlay.add_argument(
        "--scale", type=float, default=0.15, help="【可选】水印缩放比例，默认0.15"
    )
    parser_overlay.add_argument("--start-time", type=float, help="【可选】水印开始时间")
    parser_overlay.add_argument("--end-time", type=float, help="【可选】水印结束时间")

    # 13. 本地能力 - 转码/转封装
    parser_transcode = subparsers.add_parser("transcode", help="本地视频转码/转封装")
    parser_transcode.add_argument(
        "-i", "--input", required=True, help="【必填】输入媒体文件路径或URL"
    )
    parser_transcode.add_argument("-o", "--output", help="【可选】输出文件路径")
    parser_transcode.add_argument("--format", help="【可选】目标格式，如 mp4/mkv/mov")
    parser_transcode.add_argument(
        "--codec", help="【可选】视频编码器，如 copy/h264/libx264"
    )
    parser_transcode.add_argument(
        "--bitrate", default="1500k", help="【可选】视频码率，默认1500k"
    )
    parser_transcode.add_argument(
        "--audio-codec", default="aac", help="【可选】音频编码器，默认aac"
    )
    parser_transcode.add_argument(
        "--audio-bitrate", default="128k", help="【可选】音频码率，默认128k"
    )

    args = parser.parse_args()

    # 特殊处理image_to_video的images参数，转换为字典列表
    if args.command == "image_to_video":
        images_list = []
        for img_str in args.images:
            img_dict = {}
            for pair in img_str.split(","):
                k, v = pair.split("=", 1)
                k = k.strip()
                v = v.strip()
                if k == "duration":
                    v = float(v)
                elif k in ("animation_in", "animation_out"):
                    v = float(v)
                img_dict[k] = v
            images_list.append(img_dict)
        args.images = images_list

    if (
        args.command in LOCAL_FALLBACK_COMMANDS
        or _canonical_local_only_command(args.command)
    ) and _local_fallback_reason(args):
        result = run_local_fallback(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # 创建客户端
    from amk_client import AmkClient

    client = AmkClient()

    # 执行任务
    result = asyncio.run(args.func(client, args))

    # 输出结果
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
