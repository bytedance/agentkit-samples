import json
import os
import sys
import collections
from typing import Dict, Any
from pathlib import Path
import pandas as pd
from PIL import Image
import logging
import time
import click
from chunks import upload

__all__ = ["media_list"]

COLUMNS = ["session_id", "path", "material", "timestamp"]
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


def load(session_id: str) -> pd.DataFrame:
    path = Path(f"/tmp/kickart/material_state_{session_id}.csv")
    if not path.exists():
        return pd.DataFrame(columns=COLUMNS)
    return pd.read_csv(path, header=None, names=COLUMNS)


def save(session_id: str, df: pd.DataFrame):
    path = Path(f"/tmp/kickart/material_state_{session_id}.csv")
    os.makedirs(path.parent, exist_ok=True)
    df.to_csv(path, index=False, header=False)


def remove(session_id: str):
    path = Path(f"/tmp/kickart/material_state_{session_id}.csv")
    os.remove(path)

def media_list(session_id):
    """列出所有已上传的抖音营销素材"""
    df = load(session_id)
    df = df["material"].map(lambda x: json.loads(x))
    return df.to_list()

@click.group()
def main():
    """抖音营销素材上传工具"""
    logging.info(f"[tool] >>> python3 {' '.join(sys.argv)}")


@main.command()
@click.argument("file")
@click.option("--session-id", "-s", required=True, help="会话ID")
def add(file, session_id):
    """上传抖音营销素材到远程服务器，返还上传后的素材URL"""
    # 文件校验 图片8M，视频50M
    result = validate(file)
    if not result["valid"]:
        click.echo(result)
        return
    # upload file to remote server
    matriel = upload({"file": file})

    row = collections.defaultdict()
    row["session_id"] = session_id
    row["path"] = file
    row["material"] = matriel.model_dump_json()
    row["timestamp"] = str(time.time())

    df = load(session_id)
    df.loc[len(df)] = row
    save(session_id, df)
    click.echo(matriel)


@main.command()
@click.option("--session-id", "-s", required=True, help="会话ID")
def list(session_id):
    """列出所有已上传的抖音营销素材"""
    df = load(session_id)
    df = df["material"].map(lambda x: json.loads(x))
    click.echo(df.to_list())
    return df.to_list()


@main.command()
@click.option("--session-id", "-s", required=True, help="会话ID")
def clear(session_id):
    """清空当前会话中的所有已上传的抖音营销素材"""
    remove(session_id)


if __name__ == "__main__":
    main()
