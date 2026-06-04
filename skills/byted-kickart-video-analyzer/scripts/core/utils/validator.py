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
from abc import ABC, abstractmethod
from typing import Dict, Any

from core.utils.matriel import Matriel, ImageMatriel, VideoMatriel
from core.utils.extractor import MetadataExtractor


class Validator(ABC):
    """校验器接口 (策略模式接口)"""
    @abstractmethod
    def validate(self, metadata: Matriel) -> Dict[str, Any]:
        """基于 Matriel 元数据进行校验，返回校验结果"""
        pass


class ImageValidator(Validator):
    """图片校验器 (具体策略)"""
    
    def validate(self, metadata: ImageMatriel) -> Dict[str, Any]: # type: ignore
        result = {"valid": False, "file_type": "image", "errors": [], "warnings": []}
        
        if metadata.width < 300 or metadata.height < 300:
            result["errors"].append(f"图片分辨率不足，当前为 {metadata.width}x{metadata.height}，要求至少 300x300")
        
        total_pixels = metadata.width * metadata.height
        if total_pixels > 36_000_000:
            result["errors"].append(f"图片总像素过大，当前为 {total_pixels}，要求≤36,000,000")
        
        if not result["errors"]:
            result["valid"] = True
        return result


class VideoValidator(Validator):
    """视频校验器 (具体策略)"""
    
    def validate(self, metadata: VideoMatriel) -> Dict[str, Any]: # type: ignore
        result = {"valid": False, "file_type": "video", "errors": [], "warnings": []}
        
        if metadata.width == 0 or metadata.height == 0:
            result["errors"].append("无法获取视频分辨率信息")
            return result
        
        result["valid"] = True
        return result


class ValidatorFactory:
    """校验器工厂类"""
    _extractors: Dict[str, MetadataExtractor] = {}
    _validators: Dict[str, Validator] = {}

    @classmethod
    def register(cls, extensions: set, extractor: MetadataExtractor, validator: Validator):
        for ext in extensions:
            cls._extractors[ext] = extractor
            cls._validators[ext] = validator

    @classmethod
    def get_extractor(cls, ext: str) -> MetadataExtractor | None:
        return cls._extractors.get(ext)

    @classmethod
    def get_validator(cls, ext: str) -> Validator | None:
        return cls._validators.get(ext)

    @classmethod
    def extract(cls, file_path: str) -> Matriel:
        """根据扩展名分发给具体策略进行元数据提取"""
        if not os.path.isfile(file_path):
            return VideoMatriel(id="", type="", url="", size=0, width=0, height=0, duration=0.0)

        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        extractor = cls.get_extractor(ext)
        if extractor:
            return extractor.extract(file_path)

        return VideoMatriel(id="", type="", url="", size=0, width=0, height=0, duration=0.0)

    @classmethod
    def validate(cls, file_path: str) -> Dict[str, Any]:
        """提取元数据并进行校验"""
        result = {"valid": False, "file_type": None, "errors": [], "warnings": []}
        
        if not os.path.isfile(file_path):
            result["errors"].append("文件不存在")
            return result

        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        extractor = cls.get_extractor(ext)
        validator = cls.get_validator(ext)
        
        if not extractor or not validator:
            result["errors"].append("不支持的文件格式，仅支持图片(jpg/jpeg/png)或视频(mp4/avi/mov)")
            return result

        metadata = extractor.extract(file_path)
        validation_result = validator.validate(metadata)
        
        result.update(validation_result)
        result["file_type"] = metadata.type
        
        return result


class DefaultValidator:
    """默认校验器：根据文件扩展名自动分发给对应的图片或视频校验策略"""
    @staticmethod
    def extract(file_path: str) -> Matriel:
        return ValidatorFactory.extract(file_path)
    
    @staticmethod
    def validate(file_path: str) -> Dict[str, Any]:
        return ValidatorFactory.validate(file_path)