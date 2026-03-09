"""
视频拼接工具 - 使用FFmpeg将多个分镜视频拼接为完整视频
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from typing import Dict, List

from google.adk.tools import ToolContext

logger = logging.getLogger(__name__)


async def download_video(url: str, save_path: str) -> bool:
    """
    下载视频文件

    Args:
        url: 视频URL
        save_path: 保存路径

    Returns:
        是否下载成功
    """
    try:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                response.raise_for_status()

                with open(save_path, "wb") as f:
                    while True:
                        chunk = await response.content.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)

        logger.info(f"视频下载成功: {save_path}")
        return True

    except Exception as e:
        logger.error(f"视频下载失败: {url}, 错误: {e}")
        return False


async def merge_videos_ffmpeg(
    video_files: List[str], output_path: str, add_fade: bool = True
) -> bool:
    """
    使用FFmpeg拼接视频

    Args:
        video_files: 视频文件路径列表（按顺序）
        output_path: 输出文件路径
        add_fade: 是否添加淡入淡出转场（默认True）

    Returns:
        是否拼接成功
    """
    try:
        # 创建临时文件列表
        list_file = output_path + ".list.txt"
        with open(list_file, "w") as f:
            for video_file in video_files:
                # FFmpeg需要转义特殊字符
                escaped_path = video_file.replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")

        # 构建FFmpeg命令
        if add_fade:
            # 添加淡入淡出转场（复杂滤镜）
            # 简化版：直接concat（暂时不加转场，因为需要复杂的滤镜链）
            cmd = [
                "ffmpeg",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                list_file,
                "-c",
                "copy",  # 直接复制编码（最快）
                "-y",  # 覆盖输出文件
                output_path,
            ]
        else:
            # 简单拼接
            cmd = [
                "ffmpeg",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                list_file,
                "-c",
                "copy",
                "-y",
                output_path,
            ]

        logger.info(f"执行FFmpeg拼接: {' '.join(cmd)}")

        # 执行FFmpeg命令
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            logger.info(f"✅ 视频拼接成功: {output_path}")

            # 清理临时列表文件
            try:
                os.remove(list_file)
            except Exception:
                pass

            return True
        else:
            logger.error(f"FFmpeg拼接失败: {stderr.decode()}")
            return False

    except Exception as e:
        logger.error(f"视频拼接失败: {e}", exc_info=True)
        return False


async def merge_segments(tool_context: ToolContext) -> Dict:
    """
    视频拼接工具

    从session.state读取generated_videos（已生成的视频URL列表），
    下载视频文件，使用FFmpeg拼接为完整视频，上传到TOS。

    Args:
        tool_context: 工具上下文

    Returns:
        {
            "status": "success" | "error",
            "merged_video_url": str,      # 拼接后的视频URL
            "merged_video_path": str,     # 本地路径
            "total_segments": int,        # 拼接的分镜数
            "message": str
        }
    """
    try:
        # 读取已生成的视频
        generated_videos = tool_context.state.get("generated_videos")

        if not generated_videos:
            return {
                "status": "success",
                "message": "无需拼接",
                "merged_video_url": None,
                "merged_video_path": None,
                "total_segments": 0,
            }

        # ========== 数据格式规范化 ==========
        # 兼容多种格式：字符串URL、单个字典、字典列表
        if isinstance(generated_videos, str):
            # 单个URL字符串 → 转为标准列表
            logger.info("generated_videos 为字符串URL，自动规范化")
            generated_videos = [{"segment_1": generated_videos, "segment_index": 1}]
        elif isinstance(generated_videos, dict):
            # 单个字典 → 转为列表
            logger.info("generated_videos 为单个字典，自动规范化")
            generated_videos = [generated_videos]
        elif isinstance(generated_videos, list):
            # 确保列表中每个元素都是字典
            normalized = []
            for idx, item in enumerate(generated_videos):
                if isinstance(item, str):
                    normalized.append(
                        {f"segment_{idx + 1}": item, "segment_index": idx + 1}
                    )
                elif isinstance(item, dict):
                    normalized.append(item)
                else:
                    logger.warning(f"跳过未知格式的视频数据: {type(item)}")
            generated_videos = normalized

        if len(generated_videos) == 0:
            return {
                "status": "success",
                "message": "无需拼接",
                "merged_video_url": None,
                "merged_video_path": None,
                "total_segments": 0,
            }

        # ========== 单分镜智能跳过 ==========
        if len(generated_videos) == 1:
            # 提取单个视频的URL
            video_data = generated_videos[0]
            video_url = None
            for key, value in video_data.items():
                if (
                    key != "segment_index"
                    and isinstance(value, str)
                    and value.startswith("http")
                ):
                    video_url = value
                    break

            logger.info(f"单分镜场景，跳过拼接，直接返回: {video_url}")
            return {
                "status": "success",
                "message": "无需拼接",
                "merged_video_url": video_url,
                "merged_video_path": None,
                "total_segments": 1,
            }

        logger.info(f"开始拼接{len(generated_videos)}个视频片段...")

        # 按segment_index排序
        sorted_videos = sorted(
            generated_videos,
            key=lambda x: x.get("segment_index", 0) if isinstance(x, dict) else 0,
        )

        # 创建临时目录
        temp_dir = tempfile.mkdtemp(prefix="video_recreation_")
        logger.info(f"临时目录: {temp_dir}")

        # 下载所有视频片段
        downloaded_files = []

        for idx, video_data in enumerate(sorted_videos):
            # 提取视频URL（video_data是dict，格式：{"segment_1": "url"}）
            segment_name = (
                list(video_data.keys())[0]
                if isinstance(video_data, dict) and len(video_data) > 1
                else f"segment_{idx + 1}"
            )
            video_url = (
                video_data.get(segment_name)
                if isinstance(video_data, dict)
                else video_data
            )

            # 如果video_data直接包含segment_x作为key
            if isinstance(video_data, dict):
                for key in video_data.keys():
                    if key.startswith("segment_"):
                        segment_name = key
                        video_url = video_data[key]
                        break

            if not video_url or not isinstance(video_url, str):
                logger.warning(f"跳过无效的视频数据: {video_data}")
                continue

            # 下载视频
            file_ext = ".mp4"  # 默认mp4
            local_path = os.path.join(temp_dir, f"{segment_name}{file_ext}")

            success = await download_video(video_url, local_path)

            if success:
                downloaded_files.append(local_path)
            else:
                logger.error(f"下载{segment_name}失败，拼接将不包含此片段")

        if not downloaded_files:
            return {
                "status": "error",
                "message": "所有视频片段下载失败",
                "merged_video_url": None,
                "merged_video_path": None,
                "total_segments": 0,
            }

        if len(downloaded_files) < len(generated_videos):
            logger.warning(
                f"部分视频下载失败：{len(downloaded_files)}/{len(generated_videos)}"
            )

        # 拼接视频
        output_filename = "recreated_video_merged.mp4"
        output_path = os.path.join(temp_dir, output_filename)

        merge_success = await merge_videos_ffmpeg(
            video_files=downloaded_files,
            output_path=output_path,
            add_fade=False,  # 暂时不加转场，直接拼接
        )

        if not merge_success:
            return {
                "status": "error",
                "message": "视频拼接失败（FFmpeg错误）",
                "merged_video_url": None,
                "merged_video_path": None,
                "total_segments": len(downloaded_files),
            }

        # TODO: 上传到TOS（需要集成TOS上传工具）
        # 暂时返回本地路径
        # from video_breakdown_agent.tools.video_upload import video_upload_to_tos
        # tos_url = await video_upload_to_tos(output_path, tool_context)

        # 存入session state
        tool_context.state["recreated_video_path"] = output_path
        tool_context.state["recreated_video_url"] = (
            f"file://{output_path}"  # 临时使用本地路径
        )

        logger.info(f"✅ 视频拼接完成: {output_path}")

        return {
            "status": "success",
            "merged_video_url": f"file://{output_path}",  # TODO: 改为TOS URL
            "merged_video_path": output_path,
            "total_segments": len(downloaded_files),
            "message": f"成功拼接{len(downloaded_files)}个视频片段",
        }

    except Exception as e:
        logger.error(f"视频拼接失败: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"视频拼接失败: {str(e)}",
            "merged_video_url": None,
            "merged_video_path": None,
            "total_segments": 0,
        }
