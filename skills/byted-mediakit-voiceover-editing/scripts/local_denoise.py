#!/usr/bin/env python3
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

"""
Local 人声降噪：使用 ffmpeg 内置滤镜。
"""

from __future__ import annotations

from pathlib import Path

from ffmpeg_utils import denoise_audio


def denoise_voice(
    input_audio: Path,
    output_audio: Path,
    method: str = "afftdn",
) -> Path:
    """
    本地人声降噪。

    method:
      - afftdn: FFT 降噪（推荐，稳态噪声效果好）
      - anlmdn: 非局部均值降噪（保真度更高）
      - combined: highpass+lowpass+afftdn（最强降噪，可能有失真）
    """
    return denoise_audio(input_audio, output_audio, method=method)
