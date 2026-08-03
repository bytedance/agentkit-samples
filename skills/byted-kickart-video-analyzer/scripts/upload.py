# Copyright (c) 2026 ByteDance Ltd. and/or its affiliates
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

import math
from typing import Dict, Any

import click
import logging
import sys
import os

from core import Result
from core.api.meida.media import SimpleMediaService
from core.utils.extractor import VideoMetadataExtractor
from core.utils.validator import Validator
from core.api.meida.chunks import VideoMatriel


class DurationLimitedVideoValidator(Validator):
    """带时长限制的视频校验器 (具体策略)"""

    MAX_DURATION = 60  # 视频最大时长限制（秒）
    MAX_SIZE = 50 * 1024 * 1024  # 视频最大文件大小（50MB）
    MIN_RESOLUTION = 480  # 最小分辨率（480p）
    SUPPORTED_FORMATS = {"mp4", "mov"}  # 支持的视频格式
    SUPPORTED_ASPECT_RATIOS = [
        (9, 16),  # 9:16
        (16, 9),  # 16:9
        (3, 4),  # 3:4
        (4, 3),  # 4:3
        (1, 1),  # 1:1
    ]

    def validate(self, metadata: VideoMatriel) -> Dict[str, Any]:  # type: ignore
        result = {"valid": False, "file_type": "video", "errors": [], "warnings": []}

        if metadata.width == 0 or metadata.height == 0:
            result["errors"].append("无法获取视频分辨率信息")
            return result

        # 检查文件大小
        if metadata.size is not None and metadata.size > self.MAX_SIZE:
            size_mb = metadata.size / (1024 * 1024)
            result["errors"].append(
                f"文件大小超过50MB限制，当前大小为 {size_mb:.2f} MB"
            )

        # 检查视频时长是否超过60秒
        duration = 1 + math.floor(metadata.duration)
        if duration > self.MAX_DURATION:
            result["errors"].append(
                f"视频时长超过60秒限制，当前时长为 {duration:.2f} 秒"
            )

        # 检查分辨率是否≥480p
        min_dimension = min(metadata.width, metadata.height)
        if min_dimension < self.MIN_RESOLUTION:
            result["errors"].append(
                f"视频分辨率低于480p限制，当前分辨率为 {metadata.width}x{metadata.height}"
            )

        # 检查视频比例是否符合要求
        if metadata.width > 0 and metadata.height > 0:
            aspect_ratio = metadata.width / metadata.height
            supported_ratios_str = [f"{w}:{h}" for w, h in self.SUPPORTED_ASPECT_RATIOS]

            # 检查是否在支持的比例范围内（允许±5%误差）
            is_valid_ratio = False
            for width_ratio, height_ratio in self.SUPPORTED_ASPECT_RATIOS:
                expected_ratio = width_ratio / height_ratio
                if abs(aspect_ratio - expected_ratio) / expected_ratio < 0.05:
                    is_valid_ratio = True
                    break

            if not is_valid_ratio:
                result["errors"].append(
                    f"视频比例不符合要求，当前比例约为 {metadata.width}:{metadata.height}，仅支持 {', '.join(supported_ratios_str)} 比例"
                )

        if not result["errors"]:
            result["valid"] = True
        return result


@click.command()
@click.option("--file", required=True, type=str, help="本地视频文件绝对路径")
def main(file):
    """本地视频文件上传工具，上传视频并获取媒资ID"""
    logging.info(f"[tool] >>> python3 {' '.join(sys.argv)}")

    # 检查文件是否存在
    if not os.path.isfile(file):
        click.echo(
            Result(code="-1", message=f"文件不存在: {file}").model_dump_json(), err=True
        )
        exit(1)

    try:
        # 创建媒体服务实例
        media_service = SimpleMediaService()

        # 创建元数据提取器和校验器
        extractor = VideoMetadataExtractor()
        validator = DurationLimitedVideoValidator()

        # 上传视频文件
        click.echo(f"正在上传视频文件: {file}")
        matriel = media_service.add_media(file, extractor, validator)
        click.echo(Result(code="0", message="success", data=matriel).model_dump_json())
    except Exception as e:
        click.echo(Result(code="-1", message=str(e)).model_dump_json(), err=True)
        exit(1)


if __name__ == "__main__":
    main()
