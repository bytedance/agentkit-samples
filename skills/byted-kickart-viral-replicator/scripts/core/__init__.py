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
