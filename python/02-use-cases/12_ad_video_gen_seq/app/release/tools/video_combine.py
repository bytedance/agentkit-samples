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

import urllib.parse
import os
import random
import tempfile
import uuid
from typing import List
from typing import Optional

import aiohttp
from moviepy import CompositeVideoClip, VideoFileClip
from veadk.config import veadk_environments  # noqa
from veadk.utils.logger import get_logger

from app.utils import url_shortener

logger = get_logger(__name__)


def resolve_short_url(code: str) -> str:
    return url_shortener.code2url(code)


async def video_combine(video_codes: List[str]) -> Optional[str]:
    """
    合并多个视频URL为一个视频文件

    Args:
        video_codes: 视频code列表（⌥code格式）

    Returns:
        合并后的视频文件路径，如果合并失败则返回None
    """

    # 获取项目根目录
    current_dir = os.path.abspath(__file__)
    project_root = os.path.dirname(current_dir)
    for _ in range(3):  # 向上三级目录到达项目根目录
        project_root = os.path.dirname(project_root)

    # 创建输出目录在项目根目录下
    output_dir = os.path.join(project_root, "merged_videos")
    os.makedirs(output_dir, exist_ok=True)
    temp_dir = tempfile.mkdtemp(dir=output_dir)
    logger.info(f"Created temporary directory: {temp_dir}")

    # 解析短链接
    resolved_urls = []
    for code in video_codes:
        resolved_url = resolve_short_url(code)
        # 仅允许 http/https 协议，降低 SSRF 风险
        parsed = urllib.parse.urlparse(resolved_url)
        if parsed.scheme not in {"http", "https"}:
            logger.warning(f"Skip non-http(s) URL: {resolved_url}")
            continue
        resolved_urls.append(resolved_url)

    # 下载视频文件
    downloaded_files = []

    async with aiohttp.ClientSession() as session:
        for idx, code in enumerate(resolved_urls):
            try:
                # 下载视频
                logger.info(
                    f"Downloading video {idx + 1}/{len(resolved_urls)} from {code}"
                )

                async with session.get(code, allow_redirects=True) as response:
                    response.raise_for_status()
                    # 预检查内容大小，防止极端大文件下载
                    content_length = response.headers.get("content-length")
                    max_file_size = 512 * 1024 * 1024  # 512MB 上限
                    if content_length is not None:
                        try:
                            if int(content_length) > max_file_size:
                                logger.error(
                                    f"Video size {int(content_length)} exceeds limit {max_file_size}."
                                )
                                return None
                        except Exception:
                            # 如果 content-length 无法解析，继续按流式大小校验
                            pass

                    # 从content-type提取文件扩展名
                    content_type = response.headers.get("content-type", "")
                    file_extension = ".mp4"  # 默认扩展名
                    if "video" in content_type:
                        if "mp4" in content_type:
                            file_extension = ".mp4"
                        elif "webm" in content_type:
                            file_extension = ".webm"
                        elif "ogg" in content_type:
                            file_extension = ".ogg"
                        elif "mov" in content_type:
                            file_extension = ".mov"

                    # 生成简单的随机文件名
                    temp_file_path = os.path.join(
                        temp_dir,
                        f"video_{random.randint(100000, 999999)}{file_extension}",
                    )

                    # 按流式传输进行大小限制（兜底）
                    max_file_size = 512 * 1024 * 1024  # 512MB
                    total_size = 0

                    with open(temp_file_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(8192):
                            if chunk:
                                total_size += len(chunk)
                                if total_size > max_file_size:
                                    logger.error(
                                        "Video size exceeds 10GB. Download stopped."
                                    )
                                    return None
                                f.write(chunk)

                if (
                    os.path.exists(temp_file_path)
                    and os.path.getsize(temp_file_path) > 0
                ):
                    downloaded_files.append(temp_file_path)
                    logger.info(
                        f"Successfully downloaded video {idx + 1} to {temp_file_path}, size: {total_size / 1024 / 1024:.2f} MB"
                    )
                else:
                    logger.error(
                        f"Failed to download video {idx + 1}: file is empty or doesn't exist"
                    )
                    return None

            except Exception as e:
                logger.error(f"Error downloading video {idx + 1} from {code}: {e}")
                return None

    if not downloaded_files:
        logger.error("No videos were successfully downloaded")
        return None

    try:
        # 合并视频
        logger.info(f"Starting to merge {len(downloaded_files)} videos")

        # 加载所有视频片段
        video_clips = []
        start_times = []
        clip_start_time = 0.0

        try:
            for file_path in downloaded_files:
                start_times.append(clip_start_time)

                clip = VideoFileClip(file_path)
                video_clips.append(clip)

                clip_start_time += clip.duration

            clips = []
            for video_clip, start_time in zip(video_clips, start_times):
                positioned_clip = video_clip.with_start(start_time).with_position(
                    "center"
                )
                clips.append(positioned_clip)
            final_clip = CompositeVideoClip(clips)

            output_file_name = f"merged_video_{uuid.uuid4()}.mp4"
            output_file_path = os.path.join(temp_dir, output_file_name)

            logger.info(f"Saving merged video to {output_file_path}")
            final_clip.write_videofile(
                output_file_path, codec="libx264", audio_codec="aac", threads=4
            )
        finally:
            for clip in video_clips:
                try:
                    if hasattr(clip, "reader") and clip.reader:
                        clip.reader.close()
                    if hasattr(clip, "audio_reader") and clip.audio_reader:
                        clip.audio_reader.close_proc()
                        clip.audio_reader.close()
                    clip.close()
                except Exception as e:
                    logger.error(f"Error closing video clip: {e}")
            if "final_clip" in locals():
                try:
                    if hasattr(final_clip, "close"):
                        final_clip.close()
                except Exception as e:
                    logger.error(f"Error closing final clip: {e}")

        if os.path.exists(output_file_path) and os.path.getsize(output_file_path) > 0:
            logger.info(f"Successfully merged video to local path: {output_file_path}")
            return output_file_path
        else:
            logger.error(
                f"Merged video file is empty or doesn't exist: {output_file_path}"
            )
            return None

    except Exception as e:
        logger.error(f"Error merging videos: {e}")
        return None
