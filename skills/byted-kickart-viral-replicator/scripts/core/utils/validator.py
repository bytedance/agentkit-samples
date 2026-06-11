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


class ValidatorFactory(Validator):
    """校验器工厂 (具体策略)"""

    def __init__(self):
        super().__init__()
        self.image_validator = ImageValidator()
        self.video_validator = VideoValidator()

    def validate(self, metadata: Matriel) -> Dict[str, Any]:
        """根据视频元数据校验视频是否符合要求"""
        if metadata.type == "image":
            return self.image_validator.validate(metadata)  # type: ignore
        if metadata.type == "video":
            return self.video_validator.validate(metadata)  # type: ignore
        raise ValueError(f"不支持的文件类型 {metadata.type}")
