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
import time
import logging
from functools import cache

from pydantic import BaseModel


class Result(BaseModel):
    code: str
    message: str
    data: object = None


class MediaConfig:
    """媒体相关配置与常量"""

    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
    VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov"}

    IMAGE_MAX_SIZE = 8 * 1024 * 1024
    VIDEO_MAX_SIZE = 50 * 1024 * 1024

    IMAGE_MIN_WIDTH = 300
    IMAGE_MIN_HEIGHT = 300
    IMAGE_MAX_PIXELS = 36_000_000

    CSV_COLUMNS = ["group", "channel", "account", "path", "id", "material", "timestamp"]
    STORAGE_BASE_DIR = "/tmp/openclaw/byted-kickart-viral-replicator/media"


@cache
def init():
    """只执行一次的初始化方法，用于配置日志和目录"""
    log_dir = "/tmp/openclaw/byted-kickart-viral-replicator/logs"
    os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        filename=f"{log_dir}/info.{time.strftime('%Y%m%d', time.localtime())}.log",
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


init()

__all__ = ["Result"]
