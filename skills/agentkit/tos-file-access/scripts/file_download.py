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

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional
from urllib.parse import unquote, urlparse

import requests

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if not logger.handlers:
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(message)s")
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


def file_download(
    url: List[str], save_dir: Optional[str] = None, filename: Optional[List[str]] = None
) -> List[str]:
    """
    Batch download files from the internet to local storage, supporting simultaneous download of multiple URLs to avoid agent loop calls

    Args:
        url: List of file URLs (can be a single-URL list or multiple URLs)
        save_dir: Save directory, defaults to /tmp
        filename: List of filenames to save; if None, filenames will be extracted from URLs

    Returns:
        List[str]: List of absolute paths to downloaded files

    Raises:
        requests.exceptions.RequestException: Network request failure
        IOError: File write failure
        ValueError: Parameter error

    Examples:
        # Download single file
        paths = file_download(["https://example.com/file.pdf"])

        # Batch download multiple files
        paths = file_download([
            "https://example.com/file1.pdf",
            "https://example.com/file2.jpg",
            "https://example.com/file3.json"
        ])
    """
    # Ensure url is a list
    if not isinstance(url, list):
        raise ValueError("url parameter must be a list")

    urls = url
    if save_dir is None:
        # Prefer environment variable
        save_dir = "/tmp"

    # Handle filename parameter
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

    # Download all files
    downloaded_paths = []
    for url_item, filename_item in zip(urls, filenames):
        path = _download_single_file(url_item, save_dir, filename_item)
        downloaded_paths.append(path)

    return downloaded_paths


def _download_single_file(
    url: str, save_dir: Optional[str] = None, filename: Optional[str] = None
) -> str:
    """
    Download a single file (internal helper function)

    Args:
        url: File URL
        save_dir: Save directory, defaults to /tmp
        filename: Filename to save

    Returns:
        str: Absolute path to downloaded file

    Raises:
        requests.exceptions.RequestException: Network request failure
        IOError: File write failure
    """
    # Determine save directory
    if save_dir is None:
        # Prefer environment variable
        save_dir = "/tmp"

    # Ensure save directory exists
    save_path = Path(save_dir)
    save_path.mkdir(parents=True, exist_ok=True)

    # Determine filename
    if filename is None:
        # Extract filename from URL
        parsed_url = urlparse(url)
        filename = unquote(os.path.basename(parsed_url.path))

        # If no filename in URL, use default name
        if not filename or filename == "/":
            filename = "downloaded_file"

    # Full file path
    full_path = save_path / filename

    # If file exists, add counter to avoid overwriting
    counter = 1
    original_stem = full_path.stem
    original_suffix = full_path.suffix
    while full_path.exists():
        filename = f"{original_stem}_{counter}{original_suffix}"
        full_path = save_path / filename
        counter += 1

    # Download file
    try:
        logger.info(f"Downloading: {url}")
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        # Write file
        with open(full_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        logger.info(f"Downloaded: {full_path}")
        return str(full_path.absolute())

    except requests.exceptions.RequestException as e:
        raise requests.exceptions.RequestException(f"Download failed: {str(e)}")
    except IOError as e:
        raise IOError(f"Write file failed: {str(e)}")


def main():
    """Command-line interface for file_download"""
    parser = argparse.ArgumentParser(
        description="Download files from URLs to local storage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download single file
  python file_download.py https://example.com/file.pdf
  
  # Download multiple files
  python file_download.py https://example.com/file1.pdf https://example.com/file2.jpg
  
  # Download to specific directory
  python file_download.py https://example.com/file.pdf --save-dir /workspace
  
  # Download with custom filenames
  python file_download.py https://example.com/f1.pdf https://example.com/f2.jpg --filenames doc.pdf img.jpg
        """,
    )

    parser.add_argument("urls", nargs="+", help="One or more URLs to download")

    parser.add_argument(
        "--save-dir",
        type=str,
        default="/tmp",
        help="Directory to save downloaded files (default: /tmp)",
    )

    parser.add_argument(
        "--filenames",
        nargs="+",
        default=None,
        help="Custom filenames for downloaded files (must match number of URLs)",
    )

    args = parser.parse_args()

    try:
        # Call download function
        downloaded_paths = file_download(
            url=args.urls, save_dir=args.save_dir, filename=args.filenames
        )

        # Print results (one path per line for easy parsing)
        print("\n=== Downloaded Files ===")
        for path in downloaded_paths:
            print(path)

        sys.exit(0)

    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


# Example usage
if __name__ == "__main__":
    main()
