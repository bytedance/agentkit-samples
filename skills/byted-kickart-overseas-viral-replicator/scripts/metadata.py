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
import filetype
from abc import ABC, abstractmethod

from PIL import Image
import cv2

from pydantic import BaseModel, Field


class Metadata(BaseModel):
    mimetype: str = Field(description="MIME type of the file")
    size: int = Field(description="File size in bytes")
    width: int = Field(description="Image or video width in pixels")
    height: int = Field(description="Image or video height in pixels")
    duration: float = Field(default=0.0, description="Video duration in seconds")


class MetadataExtractor(ABC):
    """Metadata extractor interface (strategy pattern)"""

    @abstractmethod
    def extract(self, path: str, **kwargs) -> Metadata:
        """Extract file metadata, return Metadata object"""
        pass

    @staticmethod
    def detect(path: str) -> str:
        """
        Detect file MIME type using filetype library.

        The filetype library detects file types by reading their magic bytes
        (file signatures) rather than relying on file extensions.

        Args:
            path: File path to detect

        Returns:
            MIME type string (e.g., "image/jpeg", "video/mp4")

        Raises:
            ValueError: If file type cannot be detected
        """

        # Use filetype library to detect file type
        kind = filetype.guess(path)
        if kind is None:
            raise ValueError(f"Unable to detect file type for: {path}")
        return kind.mime


class ImageMetadataExtractor(MetadataExtractor):
    """Image metadata extractor (specific strategy)"""

    def extract(self, path: str, **kwargs) -> Metadata:
        file_size = os.path.getsize(path)
        with Image.open(path) as img:
            width, height = img.size
        return Metadata(
            mimetype=kwargs.get("mimetype", self.detect(path)),
            size=file_size,
            width=width,
            height=height,
        )


class VideoMetadataExtractor(MetadataExtractor):
    def extract(self, path: str, **kwargs) -> Metadata:
        file_size = os.path.getsize(path)

        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise ValueError(f"Failed to open video file {path}")
        try:
            # Get video stream properties
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            # Calculate video stream duration from frames
            video_duration = frame_count / fps if fps > 0 else 0.0

            # Try to get audio stream duration using OpenCV's CAP_PROP_POS_MSEC
            # This gives the total duration considering both streams
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_count - 1 if frame_count > 0 else 0)
            last_frame_time_ms = cap.get(cv2.CAP_PROP_POS_MSEC) or 0.0
            audio_duration = last_frame_time_ms / 1000.0

            # Use the maximum of video and audio duration
            # This handles cases where audio track is longer than video or vice versa
            duration = max(video_duration, audio_duration)

            return Metadata(
                mimetype=kwargs.get("mimetype", self.detect(path)),
                size=file_size,
                width=width,
                height=height,
                duration=duration,
            )
        finally:
            cap.release()


class MetadataExtractorFactory(MetadataExtractor):
    """Metadata extractor factory (strategy pattern)"""

    def __init__(self):
        self.extractors = dict()
        self.extractors["image"] = ImageMetadataExtractor()
        self.extractors["video"] = VideoMetadataExtractor()

    def extract(self, path: str, **kwargs) -> Metadata:
        """Extract file metadata, return Metadata object"""
        mine = self.detect(path)
        if "video" in mine:
            return self.extractors["video"].extract(path)
        if "image" in mine:
            return self.extractors["image"].extract(path)
        raise ValueError(
            f"Unknown file type {os.path.splitext(path)[1]}! Please check the file format."
        )
