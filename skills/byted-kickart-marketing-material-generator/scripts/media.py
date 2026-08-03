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

import json
import os
import sys
import time
import logging
import collections
import click
from typing import Dict, Any
from pathlib import Path
import pandas as pd
from PIL import Image

from .base import Result
from .chunks import upload

__all__ = ["media_list"]

COLUMNS = ["group", "channel", "account", "path", "id", "material", "timestamp"]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov"}

IMAGE_MAX_SIZE, VIDEO_MAX_SIZE = 8 * 1024 * 1024, 50 * 1024 * 1024
IMAGE_MIN_WIDTH, IMAGE_MIN_HEIGHT, IMAGE_MAX_PIXELS = 300, 300, 36_000_000


def validate(file_path: str) -> Dict[str, Any]:
    """
    校验图片/视频文件是否合法。

    返回示例：
    {
        "valid": True,
        "file_type": "image",
        "errors": [],
        "warnings": []
    }
    """
    result = {"valid": False, "file_type": None, "errors": [], "warnings": []}

    if not os.path.isfile(file_path):
        result["errors"].append("文件不存在")
        return result

    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    file_size = os.path.getsize(file_path)

    # 图片校验
    if ext in IMAGE_EXTENSIONS:
        result["file_type"] = "image"

        if file_size > IMAGE_MAX_SIZE:
            result["warnings"].append("图片单张大小建议≤8MB")
            return result

        try:
            with Image.open(file_path) as img:
                width, height = img.size
                total_pixels = width * height

                if width < IMAGE_MIN_WIDTH or height < IMAGE_MIN_HEIGHT:
                    result["errors"].append(
                        f"图片分辨率不足，当前为 {width}x{height}，要求至少 300x300"
                    )

                if total_pixels > IMAGE_MAX_PIXELS:
                    result["errors"].append(
                        f"图片总像素过大，当前为 {total_pixels}，要求≤36,000,000"
                    )
                result["valid"] = True
                return result
        except Exception as e:
            result["errors"].append(f"无法读取图片文件: {e}")
            return result

    # 视频校验
    if ext in VIDEO_EXTENSIONS:
        result["file_type"] = "video"

        if file_size > VIDEO_MAX_SIZE:
            result["errors"].append("视频文件大小超过 50MB")
            return result

        result["valid"] = True
        return result

    result["errors"].append(
        "不支持的文件格式，仅支持图片(jpg/jpeg/png)或视频(mp4/avi/mov)"
    )
    return result


def load(group: str) -> pd.DataFrame:
    path = Path(f"/tmp/openclaw/highlightvideo/media/{group}.csv")
    if not path.exists():
        return pd.DataFrame(columns=COLUMNS)
    return pd.read_csv(path, header=None, names=COLUMNS)


def save(group: str, df: pd.DataFrame):
    path = Path(f"/tmp/openclaw/highlightvideo/media/{group}.csv")
    os.makedirs(path.parent, exist_ok=True)
    df.to_csv(path, index=False, header=False)


@click.group()
def main():
    """抖音营销素材上传工具"""
    logging.info(f"[tool] >>> python3 {' '.join(sys.argv)}")


@main.command()
@click.argument("file")
@click.option("--group", required=True, type=str, help="素材所属的素材组，全局唯一")
@click.option(
    "--metadata", required=True, type=str, help="当前消息的完整未修改元信息，json格式"
)
def add(file, group, metadata):
    """上传抖音营销素材到远程服务器，返还上传后的素材ID"""
    metadata = json.loads(metadata)
    # 文件校验 图片8M，视频50M
    result = validate(file)
    if not result["valid"]:
        click.echo(result)
        return
    # upload file to remote server
    matriel = upload({"file": file})

    row = collections.defaultdict()
    row["group"] = group
    row["channel"] = metadata["channel"]
    row["account"] = metadata["chat_id"]
    row["path"] = file
    row["id"] = matriel.id  # type: ignore
    row["material"] = matriel.model_dump_json()
    row["timestamp"] = str(time.time())

    df = load(group=group)
    df.loc[len(df)] = row
    save(group, df)
    click.echo(matriel)


def media_list(group: str) -> list[Result]:
    """列出当前分组中所有已上传的抖音营销素材"""
    df = load(group=group)
    df = df["material"].map(lambda x: json.loads(x))  # type: ignore
    return df.to_list()


@main.command()
@click.option("--group", required=True, type=str, help="素材所属的素材组，全局唯一")
def list(group):
    """列出当前分组中所有已上传的抖音营销素材"""
    click.echo(media_list(group))


@main.command()
@click.option("--group", required=True, type=str, help="素材所属的素材组，全局唯一")
def clear(group):
    """清空当前分组中所有已上传的抖音营销素材"""
    path = Path(f"/tmp/openclaw/highlightvideo/media/{group}.csv")
    os.remove(path)


@main.command()
@click.option("--id", required=True, type=str, help="素材ID")
@click.option("--group", required=True, type=str, help="素材所属的素材组，全局唯一")
def remove(id, group):
    """移除指定的素材"""
    df = load(group=group)
    df.drop(df[df["id"].eq(id)].index, inplace=True)
    path = Path(f"/tmp/openclaw/highlightvideo/media/{group}.csv")
    df.to_csv(path, index=False, header=False)


if __name__ == "__main__":
    main()
