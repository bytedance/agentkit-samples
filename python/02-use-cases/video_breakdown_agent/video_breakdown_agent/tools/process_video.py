"""
视频预处理工具（自包含）
将 video-breakdown-master 后端服务的 FFmpeg + ASR + TOS 逻辑
直接内嵌到一个 VeADK tool 函数中，无需外部后端服务。

迁移来源:
- video-breakdown-master/app/services/media_processor.py
- video-breakdown-master/app/services/asr_service.py
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import os

import httpx
import tos
from tos import HttpMethodType
from google.adk.tools import ToolContext

logger = logging.getLogger(__name__)

# ==================== 数据结构 ====================


@dataclass
class SegmentAsset:
    """单个时间片段的资源信息"""

    index: int
    start: float
    end: float
    frame_paths: List[Path] = field(default_factory=list)
    frame_urls: List[str] = field(default_factory=list)
    clip_path: Optional[Path] = None
    clip_url: Optional[str] = None
    is_speech: bool = True
    speech_text: Optional[str] = None


# ==================== FFmpeg 路径自动检测 ====================


def _resolve_ffmpeg_paths() -> tuple[str, Optional[str]]:
    """
    自动检测 ffmpeg / ffprobe 可执行文件路径。

    优先级：
      1. 环境变量 / config.yaml 显式指定（仅当对应文件真实存在时）
      2. 系统 PATH（shutil.which）
      3. imageio-ffmpeg Python 包自带的二进制（随 uv 安装，无需系统装 FFmpeg）

    Returns:
        (ffmpeg_bin, ffprobe_bin) — ffprobe_bin 为 None 时将使用 ffmpeg 回退探测
    """
    # -- ffmpeg --
    env_ffmpeg = os.getenv("FFMPEG_BIN")
    ffmpeg_bin = None

    # 检查环境变量指定的路径是否真实可用
    if env_ffmpeg and shutil.which(env_ffmpeg):
        ffmpeg_bin = env_ffmpeg
    elif shutil.which("ffmpeg"):
        ffmpeg_bin = shutil.which("ffmpeg")

    # 回退到 imageio-ffmpeg Python 包内置的二进制
    if not ffmpeg_bin:
        try:
            import imageio_ffmpeg

            ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
            logger.info(f"系统无 FFmpeg，使用 imageio-ffmpeg 内置: {ffmpeg_bin}")
        except ImportError:
            ffmpeg_bin = "ffmpeg"  # 最终回退，让后续报错更清晰
            logger.warning("未找到 FFmpeg：系统 PATH 中没有，imageio-ffmpeg 包也未安装")

    # -- ffprobe --
    env_ffprobe = os.getenv("FFMPEG_FFPROBE_BIN") or os.getenv("FFPROBE_BIN")
    ffprobe_bin = None

    if env_ffprobe and shutil.which(env_ffprobe):
        ffprobe_bin = env_ffprobe
    elif shutil.which("ffprobe"):
        ffprobe_bin = shutil.which("ffprobe")
    # imageio-ffmpeg 不包含 ffprobe，ffprobe_bin 保持 None → 回退到 ffmpeg -i 解析

    return ffmpeg_bin, ffprobe_bin


# ==================== FFmpeg 辅助函数 ====================


def _run_command(cmd: List[str]) -> str:
    """执行外部命令"""
    process = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    return process.stdout.strip()


def _probe_video(
    ffprobe_bin: Optional[str], ffmpeg_bin: str, video_path: Path
) -> Dict[str, Any]:
    """
    获取视频元数据。

    优先使用 ffprobe（结构化 JSON 输出更准确），
    回退到 ffmpeg -i 解析 stderr（imageio-ffmpeg 不含 ffprobe 时）。
    """
    if ffprobe_bin:
        return _probe_with_ffprobe(ffprobe_bin, video_path)
    return _probe_with_ffmpeg(ffmpeg_bin, video_path)


def _probe_with_ffprobe(ffprobe_bin: str, video_path: Path) -> Dict[str, Any]:
    """使用 ffprobe 获取视频元数据（首选方式）"""
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

    duration = 0.0
    width = None
    height = None
    frame_rate = None

    format_info = info.get("format") or {}
    if "duration" in format_info:
        duration = float(format_info["duration"])

    for stream in info.get("streams", []):
        if stream.get("codec_type") == "video":
            width = stream.get("width")
            height = stream.get("height")
            frame_rate = stream.get("r_frame_rate")
            break

    return {
        "duration": duration,
        "width": width,
        "height": height,
        "frame_rate": frame_rate,
        "size": format_info.get("size"),
        "bit_rate": format_info.get("bit_rate"),
    }


def _probe_with_ffmpeg(ffmpeg_bin: str, video_path: Path) -> Dict[str, Any]:
    """
    使用 ffmpeg -i 解析 stderr 获取视频元数据（ffprobe 不可用时的回退方案）。

    imageio-ffmpeg 只包含 ffmpeg 不包含 ffprobe，此函数确保仍可正常工作。
    """
    import re

    # ffmpeg -i 不指定输出文件时退出码为 1，元数据输出在 stderr
    # 注意：不能加 -v error，否则会屏蔽 Duration/Stream 等 info 级别元数据，
    #       而 "At least one output file must be specified" 是 error 级别不被屏蔽，
    #       导致 stderr 非空但无法解析出元数据。
    cmd = [ffmpeg_bin, "-i", str(video_path), "-hide_banner"]
    process = subprocess.run(cmd, capture_output=True, text=True)
    stderr = process.stderr

    duration = 0.0
    width = None
    height = None
    frame_rate = None

    # 解析 Duration: HH:MM:SS.ms
    dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)", stderr)
    if dur_match:
        h, m, s, cs = dur_match.groups()
        duration = int(h) * 3600 + int(m) * 60 + int(s) + int(cs) / 100

    # 解析 Stream #0:0: Video: ... 1920x1080 ...
    res_match = re.search(r"Stream.*Video.*?(\d{2,5})x(\d{2,5})", stderr)
    if res_match:
        width = int(res_match.group(1))
        height = int(res_match.group(2))

    # 解析帧率 ... 30 fps / 29.97 tbr
    fps_match = re.search(r"(\d+(?:\.\d+)?)\s+(?:fps|tbr)", stderr)
    if fps_match:
        frame_rate = fps_match.group(1)

    logger.info(
        f"ffmpeg 探测: duration={duration}s, {width}x{height}, fps={frame_rate}"
    )
    return {
        "duration": duration,
        "width": width,
        "height": height,
        "frame_rate": frame_rate,
        "size": None,
        "bit_rate": None,
    }


def _extract_audio_sync(ffmpeg_bin: str, video_path: Path) -> Optional[Path]:
    """提取音频轨（同步版本，由 asyncio.to_thread 调用）"""
    output_path = video_path.parent / f"{video_path.stem}.mp3"
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-codec:a",
        "libmp3lame",
        "-b:a",
        "128k",
        str(output_path),
    ]
    try:
        _run_command(cmd)
        return output_path
    except Exception as exc:
        logger.warning(f"音频提取失败: {exc}")
        return None


def _build_segments(duration: float) -> List[SegmentAsset]:
    """
    固定时长分镜方案：
    - 0-3s, 3-5s, 5-10s, 10-20s, 之后每10s一段
    """
    segments: List[SegmentAsset] = []
    idx = 1

    breakpoints = [0.0, 3.0, 5.0, 10.0, 20.0]

    for i in range(len(breakpoints) - 1):
        start = breakpoints[i]
        end = breakpoints[i + 1]
        if duration <= start:
            break
        actual_end = min(end, duration)
        if actual_end - start < 0.5:
            break
        segments.append(SegmentAsset(index=idx, start=start, end=actual_end))
        idx += 1

    if duration > 20.0:
        cursor = 20.0
        while cursor < duration:
            candidate_end = min(duration, cursor + 10.0)
            if candidate_end - cursor < 0.5:
                break
            segments.append(SegmentAsset(index=idx, start=cursor, end=candidate_end))
            idx += 1
            cursor = candidate_end

    return segments


def _assign_asr_text_to_segments(
    segments: List[SegmentAsset],
    asr_segments: List[Dict[str, Any]],
) -> None:
    """将 ASR 识别的文本按时间重叠分配到分镜"""
    for segment in segments:
        texts = []
        for asr_seg in asr_segments:
            asr_start = asr_seg.get("start", 0.0)
            asr_end = asr_seg.get("end", 0.0)
            text = asr_seg.get("text", "").strip()
            if not text:
                continue
            overlap_start = max(segment.start, asr_start)
            overlap_end = min(segment.end, asr_end)
            if overlap_end > overlap_start:
                texts.append(text)
        if texts:
            segment.is_speech = True
            segment.speech_text = " ".join(texts)
        else:
            segment.is_speech = False
            segment.speech_text = None


def _extract_segment_frames(
    ffmpeg_bin: str,
    video_path: Path,
    segment: SegmentAsset,
    frames_per_segment: int = 3,
) -> None:
    """提取单个分镜的关键帧"""
    frames_dir = video_path.parent / "frames"
    frames_dir.mkdir(exist_ok=True)
    seg_duration = max(segment.end - segment.start, 0.5)
    safe_margin = 0.1

    for i in range(frames_per_segment):
        ratio = i / max(frames_per_segment - 1, 1)
        raw_offset = segment.start + ratio * seg_duration
        offset = min(raw_offset, segment.end - safe_margin)
        offset = max(offset, segment.start)
        output_path = frames_dir / f"seg{segment.index:03d}_frame_{i}.jpg"

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
            "8",  # 降低质量减小文件体积（2=最高质量，31=最低质量）
            str(output_path),
        ]
        try:
            _run_command(cmd)
            if output_path.exists():
                segment.frame_paths.append(output_path)
        except Exception as exc:
            logger.warning(f"片段 {segment.index} 第{i}帧提取失败: {exc}")


def _extract_single_clip(
    ffmpeg_bin: str,
    video_path: Path,
    segment: SegmentAsset,
    clips_dir: Path,
) -> None:
    """切割单个视频片段"""
    duration = segment.end - segment.start
    output_path = clips_dir / f"seg{segment.index:03d}_clip.mp4"

    cmd = [
        ffmpeg_bin,
        "-y",
        "-ss",
        f"{segment.start:.2f}",
        "-i",
        str(video_path),
        "-t",
        f"{duration:.2f}",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-b:v",
        "1000k",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    try:
        _run_command(cmd)
        segment.clip_path = output_path
    except Exception as exc:
        logger.warning(f"片段 {segment.index} 切割失败: {exc}")
        segment.clip_path = None


# ==================== ASR 辅助函数 ====================


async def _transcribe_audio(audio_url: str) -> Optional[Dict[str, Any]]:
    """
    调用火山引擎 ASR 获取音轨文本（提交 + 轮询）
    配置不全时静默跳过（优雅降级）
    """
    # VeADK 扁平化: asr.app_id → ASR_APP_ID; 兼容旧名 VOLC_ASR_*
    app_id = os.getenv("ASR_APP_ID") or os.getenv("VOLC_ASR_APP_ID", "")
    access_key = os.getenv("ASR_ACCESS_KEY") or os.getenv("VOLC_ASR_ACCESS_KEY", "")
    resource_id = os.getenv("ASR_RESOURCE_ID") or os.getenv(
        "VOLC_ASR_RESOURCE_ID", "volc.bigasr.auc"
    )
    submit_endpoint = os.getenv(
        "ASR_ENDPOINT",
    ) or os.getenv(
        "VOLC_ASR_ENDPOINT",
        "https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit",
    )
    query_endpoint = os.getenv(
        "ASR_QUERY_ENDPOINT",
    ) or os.getenv(
        "VOLC_ASR_QUERY_ENDPOINT",
        "https://openspeech.bytedance.com/api/v3/auc/bigmodel/query",
    )

    if not app_id or not access_key:
        logger.info(
            "未配置火山 ASR（VOLC_ASR_APP_ID / VOLC_ASR_ACCESS_KEY），跳过语音识别"
        )
        return None

    request_id = str(uuid.uuid4())
    headers = {
        "Content-Type": "application/json",
        "X-Api-App-Key": app_id,
        "X-Api-Access-Key": access_key,
        "X-Api-Resource-Id": resource_id,
        "X-Api-Request-Id": request_id,
        "X-Api-Sequence": "-1",
    }
    payload = {
        "user": {"uid": "video-breakdown-agent"},
        "audio": {"url": audio_url, "format": "mp3"},
        "request": {
            "model_name": "bigmodel",
            "enable_itn": True,
            "enable_punc": True,
            "show_utterances": True,
        },
    }

    try:
        # 提交任务
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(submit_endpoint, headers=headers, json=payload)
            resp.raise_for_status()

        logger.info(f"ASR 任务已提交 request_id={request_id}")
        await asyncio.sleep(5.0)

        # 轮询结果
        max_attempts = 15
        for attempt in range(1, max_attempts + 1):
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(query_endpoint, headers=headers, json={})
                resp.raise_for_status()
                data = resp.json()

            status_code = resp.headers.get("X-Api-Status-Code")

            if status_code == "20000000":
                # 识别成功
                return _parse_asr_result(data)
            elif status_code == "20000003":
                # 静音音频
                logger.info("ASR 检测到静音音频")
                return {"text": "", "segments": []}
            elif status_code in ["20000001", "20000002"]:
                # 处理中/排队中
                logger.info(f"ASR 处理中 attempt={attempt}/{max_attempts}")
                await asyncio.sleep(3.0)
            else:
                logger.error(f"ASR 返回错误码 status_code={status_code}")
                return None

        logger.error(f"ASR 查询超时 request_id={request_id}")
    except Exception as exc:
        logger.error(f"ASR 异常: {exc}")

    return None


def _parse_asr_result(response_json: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """解析 ASR 返回结果"""
    result = response_json.get("result")
    if not result:
        return None

    text_chunks: List[str] = []
    segments: List[Dict[str, Any]] = []

    if isinstance(result, dict):
        main_text = result.get("text")
        if main_text:
            text_chunks.append(main_text.strip())

        utterances = result.get("utterances") or []
        if isinstance(utterances, list):
            for item in utterances:
                text = item.get("text")
                if text:
                    segments.append(
                        {
                            "text": text.strip(),
                            "start": (item.get("start_time") or 0) / 1000.0,
                            "end": (item.get("end_time") or 0) / 1000.0,
                        }
                    )

    merged_text = "\n".join([c for c in text_chunks if c]).strip()
    if not merged_text:
        return None

    return {"text": merged_text, "segments": segments}


# ==================== TOS 上传辅助 ====================


def _get_tos_client() -> Optional[tos.TosClientV2]:
    """创建 TOS 客户端（凭证不全时返回 None）"""
    ak = os.getenv("VOLCENGINE_ACCESS_KEY", "")
    sk = os.getenv("VOLCENGINE_SECRET_KEY", "")
    if not ak or not sk:
        try:
            from veadk.auth.veauth.utils import get_credential_from_vefaas_iam

            cred = get_credential_from_vefaas_iam()
            ak = cred.access_key_id
            sk = cred.secret_access_key
        except Exception:
            return None

    region = os.getenv("DATABASE_TOS_REGION") or os.getenv("TOS_REGION", "cn-beijing")
    endpoint = f"tos-{region}.volces.com"

    return tos.TosClientV2(ak=ak, sk=sk, endpoint=endpoint, region=region)


async def _upload_to_tos(
    client: tos.TosClientV2,
    bucket: str,
    key: str,
    content: bytes,
    content_type: str,
) -> Optional[str]:
    """上传字节到 TOS 并返回签名 URL"""
    try:
        await asyncio.to_thread(
            client.put_object,
            bucket=bucket,
            key=key,
            content=content,
            content_type=content_type,
        )
        signed = await asyncio.to_thread(
            client.pre_signed_url,
            http_method=HttpMethodType.Http_Method_Get,
            bucket=bucket,
            key=key,
            expires=604800,
        )
        return signed.signed_url
    except Exception as exc:
        logger.warning(f"TOS 上传失败 key={key}: {exc}")
        return None


# ==================== 路径判断辅助 ====================


def _resolve_local_path(video_url: str) -> Optional[Path]:
    """
    判断 video_url 是否为本地文件路径。

    支持格式：
      - 绝对路径: /path/to/video.mp4
      - file:// 协议: file:///path/to/video.mp4
      - Windows 绝对路径: C:\\path\\to\\video.mp4（兼容）

    Returns:
        Path 对象（如果是本地路径），否则 None
    """
    if not video_url:
        return None

    # file:// 协议
    if video_url.startswith("file://"):
        local_str = video_url[7:]  # 去掉 file://
        # file:///path → /path (Unix), file:///C:/path → C:/path (Windows)
        if local_str.startswith("/") and len(local_str) > 2 and local_str[2] == ":":
            local_str = local_str[1:]  # Windows: /C:/path → C:/path
        return Path(local_str)

    # Unix 绝对路径
    if video_url.startswith("/"):
        return Path(video_url)

    # Windows 绝对路径 (C:\..., D:\...)
    if len(video_url) >= 3 and video_url[1] == ":" and video_url[2] in ("/", "\\"):
        return Path(video_url)

    # 相对路径：只要能在当前工作目录解析到本地文件，也视为本地
    try:
        candidate = Path(video_url)
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    except Exception:
        pass

    # HTTP(S) URL 或其他 → 非本地
    return None


# ==================== 主工具函数 ====================


async def process_video(video_url: str, tool_context: ToolContext) -> dict:
    """
    完整视频预处理流水线，替代原后端 breakdown 服务。

    流程：下载视频 -> FFprobe 元数据 -> FFmpeg 音频提取 -> 火山 ASR 语音识别
         -> 固定时长分段 -> FFmpeg 帧提取 + 片段切割 -> TOS 上传

    需要本机安装 FFmpeg（brew install ffmpeg）。
    ASR 需配置 VOLC_ASR_APP_ID + VOLC_ASR_ACCESS_KEY，未配置时跳过语音识别。

    Args:
        video_url: 视频URL（公开URL / TOS 签名URL）或本地文件路径（/path/to/video.mp4）

    Returns:
        dict: 包含 duration, resolution, segments, audio_url, full_transcript 等
    """
    # 自动检测 ffmpeg/ffprobe 路径（系统 → imageio-ffmpeg 回退）
    ffmpeg_bin, ffprobe_bin = _resolve_ffmpeg_paths()
    # 减少帧数以降低 base64 体积（避免超过 LLM tokens 限制）
    frames_per_segment = int(
        os.getenv("FFMPEG_FRAMES_PER_SEGMENT") or os.getenv("FRAMES_PER_SEGMENT", "2")
    )
    temp_base = os.getenv("FFMPEG_MEDIA_TEMP_DIR") or os.getenv(
        "MEDIA_TEMP_DIR", "./.media-cache"
    )
    Path(temp_base).mkdir(parents=True, exist_ok=True)

    task_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    temp_dir = Path(tempfile.mkdtemp(prefix=f"media_{task_id}_", dir=temp_base))
    local_video = temp_dir / f"{task_id}.mp4"

    # TOS 配置（VeADK 扁平化: database.tos.bucket → DATABASE_TOS_BUCKET）
    bucket = os.getenv("DATABASE_TOS_BUCKET") or os.getenv(
        "TOS_BUCKET", "video-breakdown-uploads"
    )
    tos_prefix = os.getenv("TOS_OUTPUT_PREFIX", "videobreak")

    try:
        # ---- Step 1: 获取本地视频文件 ----
        # 支持本地路径（/path/to/video.mp4 或 file:///path/to/video.mp4）和 HTTP URL
        local_source = _resolve_local_path(video_url)
        if local_source:
            # 本地文件：直接复制到工作目录
            if not local_source.exists():
                return {"error": f"本地文件不存在: {local_source}"}
            file_size = local_source.stat().st_size
            max_video_size = 2 * 1024 * 1024 * 1024  # 2GB
            if file_size > max_video_size:
                return {
                    "error": f"视频文件过大（>{max_video_size // 1024 // 1024}MB），请压缩后重试"
                }
            shutil.copy2(str(local_source), str(local_video))
            logger.info(
                f"[process_video] 使用本地文件: {local_source} ({file_size / 1024 / 1024:.1f}MB)"
            )
        else:
            # HTTP URL：流式下载
            logger.info(f"[process_video] 下载视频: {video_url[:100]}...")
            max_video_size = 2 * 1024 * 1024 * 1024  # 2GB 上限
            total_downloaded = 0
            async with httpx.AsyncClient(timeout=300, follow_redirects=True) as client:
                async with client.stream("GET", video_url) as resp:
                    resp.raise_for_status()
                    with open(local_video, "wb") as f:
                        async for chunk in resp.aiter_bytes(chunk_size=65536):
                            total_downloaded += len(chunk)
                            if total_downloaded > max_video_size:
                                return {
                                    "error": f"视频文件过大（>{max_video_size // 1024 // 1024}MB），请压缩后重试"
                                }
                            f.write(chunk)
            logger.info(
                f"[process_video] 下载完成: {local_video} ({total_downloaded / 1024 / 1024:.1f}MB)"
            )

        # ---- Step 2: 元数据 ----
        metadata = await asyncio.to_thread(
            _probe_video, ffprobe_bin, ffmpeg_bin, local_video
        )
        duration = float(metadata.get("duration") or 0.0)
        if duration <= 0:
            return {"error": "无法获取视频时长，请确认视频URL有效"}
        resolution = f"{metadata.get('width')}x{metadata.get('height')}"
        logger.info(
            f"[process_video] 元数据: 时长={duration:.1f}s, 分辨率={resolution}"
        )

        # ---- Step 3: 提取音频 ----
        audio_path = await asyncio.to_thread(
            _extract_audio_sync, ffmpeg_bin, local_video
        )
        audio_url_out = None
        audio_base64 = None

        # TOS 客户端（帧/片段/音频上传）
        tos_client = _get_tos_client()

        if audio_path and tos_client:
            key = f"{tos_prefix}/{task_id}/audio/{audio_path.name}"
            audio_url_out = await _upload_to_tos(
                tos_client, bucket, key, audio_path.read_bytes(), "audio/mpeg"
            )

        # ---- Step 4: ASR 语音识别 ----
        asr_result = None
        asr_segments = None
        if audio_url_out:
            asr_result = await _transcribe_audio(audio_url_out)
            if asr_result:
                asr_segments = asr_result.get("segments", [])
                logger.info(f"[process_video] ASR 识别完成: {len(asr_segments)} 个分段")

        # ---- Step 5: 构建固定时长分镜 ----
        segments = _build_segments(duration)
        if asr_segments:
            _assign_asr_text_to_segments(segments, asr_segments)
        logger.info(f"[process_video] 分镜: {len(segments)} 个片段")

        # ---- Step 6: 提取关键帧（并发） ----
        frame_tasks = [
            asyncio.to_thread(
                _extract_segment_frames,
                ffmpeg_bin,
                local_video,
                seg,
                frames_per_segment,
            )
            for seg in segments
        ]
        await asyncio.gather(*frame_tasks)

        # ---- Step 7: 切割视频片段（并发） ----
        clips_dir = temp_dir / "clips"
        clips_dir.mkdir(exist_ok=True)
        clip_tasks = [
            asyncio.to_thread(
                _extract_single_clip, ffmpeg_bin, local_video, seg, clips_dir
            )
            for seg in segments
        ]
        await asyncio.gather(*clip_tasks)

        # ---- Step 8: 并发上传到 TOS ----
        if tos_client:
            upload_tasks = []

            for seg in segments:
                # 帧上传任务
                for fp in seg.frame_paths:
                    if fp.exists():
                        key = f"{tos_prefix}/{task_id}/frames/{fp.name}"
                        upload_tasks.append(
                            ("frame", seg, fp, key, fp.read_bytes(), "image/jpeg")
                        )
                # 片段上传任务
                if seg.clip_path and seg.clip_path.exists():
                    key = f"{tos_prefix}/{task_id}/clips/{seg.clip_path.name}"
                    upload_tasks.append(
                        (
                            "clip",
                            seg,
                            seg.clip_path,
                            key,
                            seg.clip_path.read_bytes(),
                            "video/mp4",
                        )
                    )

            # 并发上传（信号量限制并发数，避免 TOS 限流）
            tos_semaphore = asyncio.Semaphore(10)

            async def _upload_one(item):
                kind, seg, path, key, data, ct = item
                async with tos_semaphore:
                    url = await _upload_to_tos(tos_client, bucket, key, data, ct)
                    return kind, seg, url

            results = await asyncio.gather(
                *[_upload_one(t) for t in upload_tasks],
                return_exceptions=True,
            )

            for r in results:
                if isinstance(r, Exception):
                    logger.warning(f"TOS 上传异常: {r}")
                    continue
                kind, seg, url = r
                if url:
                    if kind == "frame":
                        seg.frame_urls.append(url)
                    else:
                        seg.clip_url = url

            tos_client.close()
        else:
            logger.warning("[process_video] TOS 凭证未配置，跳过上传（帧/片段仅本地）")

        # ---- Step 8b: base64 帧图回退（TOS 不可用/上传失败时） ----
        for seg in segments:
            if not seg.frame_urls and seg.frame_paths:
                for fp in seg.frame_paths:
                    if fp.exists():
                        b64 = base64.b64encode(fp.read_bytes()).decode()
                        seg.frame_urls.append(f"data:image/jpeg;base64,{b64}")
                if seg.frame_urls:
                    logger.info(
                        f"片段 {seg.index}: TOS 不可用，使用 base64 帧图 ({len(seg.frame_urls)} 张)"
                    )

        # 音频 base64 回退
        if not audio_url_out and audio_path and audio_path.exists():
            audio_base64 = base64.b64encode(audio_path.read_bytes()).decode()
            logger.info(
                f"[process_video] TOS 不可用，音频编码为 base64 ({len(audio_base64)} chars)"
            )

        # ---- 构建输出 ----
        full_transcript = None
        if asr_result and asr_result.get("text"):
            full_transcript = asr_result["text"]

        segments_output = []
        for seg in segments:
            segments_output.append(
                {
                    "index": seg.index,
                    "start": round(seg.start, 2),
                    "end": round(seg.end, 2),
                    "frame_urls": seg.frame_urls,
                    "clip_url": seg.clip_url,
                    "is_speech": seg.is_speech,
                    "speech_text": seg.speech_text,
                }
            )

        result = {
            "task_id": task_id,
            "duration": round(duration, 2),
            "resolution": resolution,
            "metadata": metadata,
            "audio_url": audio_url_out,
            "audio_base64": audio_base64,
            "full_transcript": full_transcript,
            "segment_count": len(segments_output),
            "segments": segments_output,
        }

        # 存入 session state 供后续 sub-agent 使用（完整数据含 base64）
        tool_context.state["process_video_result"] = result

        # 返回给 LLM 的瘦身版本：base64 data URL 替换为占位标记，节省 context tokens
        slim_segments = []
        for seg_out in segments_output:
            slim_seg = dict(seg_out)
            frame_urls = slim_seg.get("frame_urls", [])
            b64_count = sum(
                1 for u in frame_urls if isinstance(u, str) and u.startswith("data:")
            )
            if b64_count > 0:
                slim_seg["frame_urls"] = [
                    f"(本地帧图已缓存，共{b64_count}张，后续工具会自动读取)"
                ]
            slim_segments.append(slim_seg)

        slim_result = dict(result)
        slim_result["segments"] = slim_segments
        if audio_base64:
            slim_result["audio_base64"] = "(音频已缓存为base64，后续工具会自动读取)"

        return slim_result

    except httpx.HTTPError as exc:
        return {"error": f"视频下载失败: {exc}"}
    except subprocess.CalledProcessError as exc:
        return {
            "error": f"FFmpeg 处理失败: {exc.stderr[:300] if exc.stderr else str(exc)}"
        }
    except Exception as exc:
        logger.error(f"[process_video] 异常: {exc}", exc_info=True)
        return {"error": f"视频预处理失败: {str(exc)}"}
    finally:
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass
