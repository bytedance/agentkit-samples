import argparse
import json
import os
import sys
import collections
from typing import List, Dict, Any
from pathlib import Path
import pandas as pd
from PIL import Image
from chunks import *
from model import *

__all__ = ["list"]
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
                    result["errors"].append(f"图片分辨率不足，当前为 {width}x{height}，要求至少 300x300")

                if total_pixels > IMAGE_MAX_PIXELS:
                    result["errors"].append(f"图片总像素过大，当前为 {total_pixels}，要求≤36,000,000")
                result['valid'] = True
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
        
        result['valid'] = True
        return result

    result["errors"].append("不支持的文件格式，仅支持图片(jpg/jpeg/png)或视频(mp4/avi/mov)")
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

def add(args: argparse.Namespace) -> Matriel | None:
    # 文件校验 图片8M，视频50M
    result = validate(args.file)
    if not result['valid']:
        return print(result)
    # upload file to remote server
    matriel = upload({"file": args.file})
    
    row = collections.defaultdict()
    row['session_id'] = args.session_id
    row['path'] = args.file
    row['material'] = matriel.model_dump_json()
    row['timestamp'] = str(time.time())

    df = load(args.session_id)
    df.loc[len(df)] = row
    save(args.session_id, df)
    return matriel

def list(args: argparse.Namespace) -> List[dict]:
    df = load(args.session_id)
    df = df["material"].map(lambda x: json.loads(x))
    return df.to_list()


def clear(args: argparse.Namespace) -> None:
    remove(args.session_id)


def build() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="抖音营销素材上传工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_add = subparsers.add_parser("add", help="上传抖音营销素材到远程服务器，返还上传后的素材URL")
    p_add.add_argument("file", help="本地文件路径")
    p_add.add_argument("--session-id", "-s", required=True, help="会话ID")
    p_add.set_defaults(func=add)

    p_list = subparsers.add_parser("list", help="列出所有已上传的抖音营销素材")
    p_list.add_argument("--session-id", "-s", required=True, help="会话ID")
    p_list.set_defaults(func=list)

    p_clear = subparsers.add_parser("clear", help="清空当前会话中的所有已上传的抖音营销素材")
    p_clear.add_argument("--session-id", "-s", required=True, help="会话ID")
    p_clear.set_defaults(func=clear)

    return parser


if __name__ == "__main__":
    logging.info(f"[tool] >>> python3 {' '.join(sys.argv)}")
    args = build().parse_args()
    print(args.func(args))
