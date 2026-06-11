# Copyright 2026 ByteDance
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


import os
from abc import ABC, abstractmethod

from PIL import Image
import cv2
from core.utils.matriel import Matriel, ImageMatriel, VideoMatriel


class MetadataExtractor(ABC):
    """元数据提取器接口 (策略模式接口)"""

    @abstractmethod
    def extract(self, file_path: str) -> Matriel:
        """提取文件的元数据，返回 Matriel 对象（ImageMatriel 或 VideoMatriel）"""
        pass


class ImageMetadataExtractor(MetadataExtractor):
    """图片元数据提取器 (具体策略)"""

    def extract(self, file_path: str) -> Matriel:
        file_size = os.path.getsize(file_path)
        with Image.open(file_path) as img:
            width, height = img.size
        return ImageMatriel(
            id="", type="image", url="", size=file_size, width=width, height=height
        )


class VideoMetadataExtractor(MetadataExtractor):
    """视频元数据提取器 (具体策略)"""

    def _calculate_closest_ratio(self, width: int, height: int) -> str:
        """
        根据宽高计算最接近的标准比例

        常见视频比例：
        - 16:9 (1.777...)
        - 9:16 (0.5625)
        - 4:3 (1.333...)
        - 1:1 (1.0)
        - 3:4 (0.75)
        - 21:9 (2.333...)
        - 9:21 (0.428...)

        Args:
            width: 视频宽度
            height: 视频高度

        Returns:
            最接近的标准比例字符串，如 "16:9", "9:16", "4:3", "1:1"
        """
        if width == 0 or height == 0:
            return ""

        # 定义常见的标准比例
        standard_ratios = {
            "16:9": 16 / 9,
            "9:16": 9 / 16,
            "4:3": 4 / 3,
            "1:1": 1.0,
            "3:4": 3 / 4,
            "21:9": 21 / 9,
            "9:21": 9 / 21,
        }

        # 计算实际宽高比
        actual_ratio = width / height

        # 找到最接近的标准比例
        closest_ratio = ""
        min_diff = float("inf")
        for ratio_name, ratio_value in standard_ratios.items():
            diff = abs(actual_ratio - ratio_value)
            if diff < min_diff:
                min_diff = diff
                closest_ratio = ratio_name

        return closest_ratio

    def extract(self, file_path: str) -> Matriel:
        file_size = os.path.getsize(file_path)

        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            return VideoMatriel(
                id="",
                type="video",
                url="",
                size=file_size,
                width=0,
                height=0,
                duration=0.0,
            )
        try:
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0.0

            # 计算最接近的标准比例
            closest_ratio = self._calculate_closest_ratio(width, height)

            return VideoMatriel(
                id="",
                type="video",
                url="",
                size=file_size,
                width=width,
                height=height,
                duration=duration,
                closest_ratio=closest_ratio,
            )
        finally:
            cap.release()


class MetadataExtractorFactory(MetadataExtractor):
    """元数据提取器工厂 (具体策略)"""

    def __init__(self):
        self.image_extractor = ImageMetadataExtractor()
        self.video_extractor = VideoMetadataExtractor()

    def extract(self, file_path: str) -> Matriel:
        """根据文件路径提取元数据"""
        if file_path.endswith(
            (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif")
        ):
            return self.image_extractor.extract(file_path)
        if file_path.endswith((".mp4", ".avi", ".mov", ".wmv", ".flv")):
            return self.video_extractor.extract(file_path)
        raise ValueError(f"不支持的文件类型 {os.path.splitext(file_path)[1]}")


__all__ = [
    "MetadataExtractor",
    "ImageMetadataExtractor",
    "VideoMetadataExtractor",
    "MetadataExtractorFactory",
]
