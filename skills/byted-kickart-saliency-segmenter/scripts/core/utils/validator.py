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

from abc import ABC, abstractmethod
from typing import Dict, Any

from core.utils.matriel import Matriel, ImageMatriel, VideoMatriel


class Validator(ABC):
    """校验器接口 (策略模式接口)"""

    @abstractmethod
    def validate(self, metadata: Matriel) -> Dict[str, Any]:
        """基于 Matriel 元数据进行校验，返回校验结果"""
        pass


class ImageValidator(Validator):
    """图片校验器 (具体策略)"""

    def validate(self, metadata: ImageMatriel) -> Dict[str, Any]:  # type: ignore
        result = {"valid": False, "file_type": "image", "errors": [], "warnings": []}

        if metadata.width < 300 or metadata.height < 300:
            result["errors"].append(
                f"图片分辨率不足，当前为 {metadata.width}x{metadata.height}，要求至少 300x300"
            )

        total_pixels = metadata.width * metadata.height
        if total_pixels > 36_000_000:
            result["errors"].append(
                f"图片总像素过大，当前为 {total_pixels}，要求≤36,000,000"
            )

        if not result["errors"]:
            result["valid"] = True
        return result


class VideoValidator(Validator):
    """视频校验器 (具体策略)"""

    def validate(self, metadata: VideoMatriel) -> Dict[str, Any]:  # type: ignore
        result = {"valid": False, "file_type": "video", "errors": [], "warnings": []}

        if metadata.width == 0 or metadata.height == 0:
            result["errors"].append("无法获取视频分辨率信息")
            return result

        result["valid"] = True
        return result
