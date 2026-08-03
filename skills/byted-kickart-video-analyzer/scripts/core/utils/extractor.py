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

import os
import math
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
            duration = math.floor(frame_count / fps if fps > 0 else 0.0) + 1

            return VideoMatriel(
                id="",
                type="video",
                url="",
                size=file_size,
                width=width,
                height=height,
                duration=duration,
            )
        finally:
            cap.release()


__all__ = ["MetadataExtractor", "ImageMetadataExtractor", "VideoMetadataExtractor"]
