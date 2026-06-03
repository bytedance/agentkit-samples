# MIT License
# 
# Copyright (c) 2026 ByteDance
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

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
        
        try:    
            with Image.open(file_path) as img:
                width, height = img.size
        except Exception:
            # 如果无法读取图片，仍然返回一个包含 size 的对象，方便 validator 至少进行 size 的校验
            width, height = 0, 0
            
        return ImageMatriel(id="", type="image", url="", size=file_size, width=width, height=height)


class VideoMetadataExtractor(MetadataExtractor):
    """视频元数据提取器 (具体策略)"""
    
    def extract(self, file_path: str) -> Matriel:
        file_size = os.path.getsize(file_path)
        
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            return VideoMatriel(id="", type="video", url="", size=file_size, width=0, height=0, duration=0.0)
        try:
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = math.floor(frame_count / fps if fps > 0 else 0.0) + 1
            
            return VideoMatriel(id="", type="video", url="", size=file_size, width=width, height=height, duration=duration)
        finally:
            cap.release()



__all__ = [
    "MetadataExtractor",
    "ImageMetadataExtractor", 
    "VideoMetadataExtractor"
]