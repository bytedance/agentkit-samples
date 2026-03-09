"""
批量文件下载工具。

用法:
    python scripts/file_download.py --urls <url1> <url2> ... [--save-dir <dir>] [--filenames <name1> <name2> ...]
"""

import argparse
import json
import logging
import os
from pathlib import Path
from typing import List, Optional
from urllib.parse import unquote, urlparse

import requests

logger = logging.getLogger(__name__)


def file_download(
    url: List[str],
    save_dir: Optional[str] = None,
    filename: Optional[List[str]] = None,
) -> List[str]:
    """
    批量下载文件到本地。

    Args:
        url: URL 列表
        save_dir: 保存目录，默认 /tmp
        filename: 文件名列表，与 URL 一一对应

    Returns:
        List[str]: 下载文件的绝对路径列表
    """
    if not isinstance(url, list):
        raise ValueError("url parameter must be a list")

    urls = url
    if save_dir is None:
        save_dir = os.getenv("DOWNLOAD_DIR", "/tmp")

    if filename is None:
        filenames = [None] * len(urls)
    elif isinstance(filename, list):
        if len(filename) != len(urls):
            raise ValueError(
                f"filename list length ({len(filename)}) must match url list length ({len(urls)})"
            )
        filenames = filename
    else:
        raise ValueError("filename must be a list or None")

    downloaded_paths = []
    for url_item, filename_item in zip(urls, filenames):
        path = _download_single_file(url_item, save_dir, filename_item)
        downloaded_paths.append(path)

    return downloaded_paths


def _download_single_file(
    url: str, save_dir: Optional[str] = None, filename: Optional[str] = None
) -> str:
    if save_dir is None:
        save_dir = os.getenv("DOWNLOAD_DIR", "/tmp")

    save_path = Path(save_dir)
    save_path.mkdir(parents=True, exist_ok=True)

    if filename is None:
        parsed_url = urlparse(url)
        filename = unquote(os.path.basename(parsed_url.path))
        if not filename or filename == "/":
            filename = "downloaded_file"

    full_path = save_path / filename

    counter = 1
    original_stem = full_path.stem
    original_suffix = full_path.suffix
    while full_path.exists():
        filename = f"{original_stem}_{counter}{original_suffix}"
        full_path = save_path / filename
        counter += 1

    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        with open(full_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return str(full_path.absolute())
    except requests.exceptions.RequestException as e:
        raise requests.exceptions.RequestException(f"Download failed: {str(e)}")
    except IOError as e:
        raise IOError(f"Write file failed: {str(e)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="批量下载文件")
    parser.add_argument("--urls", nargs="+", required=True, help="URL 列表")
    parser.add_argument("--save-dir", default=None, help="保存目录")
    parser.add_argument("--filenames", nargs="+", default=None, help="文件名列表")
    args = parser.parse_args()

    paths = file_download(args.urls, args.save_dir, args.filenames)
    print(json.dumps({"downloaded": paths}, ensure_ascii=False, indent=2))
