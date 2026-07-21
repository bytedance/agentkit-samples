"""
TOS file upload tool.

Usage:
    python scripts/tos_upload.py <file_path> [--bucket <bucket_name>] [--object-key <key>] [--region <region>]
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from typing import Optional

import tos
from tos import HttpMethodType

from env_loader import load_project_env

logger = logging.getLogger(__name__)

# 默认常量。TOS bucket 必须由部署环境显式配置，避免误用其他账号的桶。
DEFAULT_BUCKET = ""
DEFAULT_REGION = "cn-beijing"
INVALID_BUCKET_VALUES = {"", "your_bucket_name", "your_bucket"}

load_project_env()


def upload_file_to_tos(
    file_path: str,
    bucket_name: Optional[str] = None,
    object_key: Optional[str] = None,
    region: Optional[str] = None,
    expires: int = 604800,
) -> Optional[str]:
    """
    上传文件到 TOS 对象存储并返回签名 URL。

    Args:
        file_path: 本地文件路径
        bucket_name: TOS 桶名（默认从环境变量或默认值）
        object_key: 存储路径（默认自动生成）
        region: 区域（默认 cn-beijing）
        expires: 签名 URL 有效期（秒，默认7天）

    Returns:
        str: 签名 URL，失败返回 None
    """
    if bucket_name is None:
        bucket_name = os.getenv("DATABASE_TOS_BUCKET", DEFAULT_BUCKET)
    if region is None:
        region = os.getenv("DATABASE_TOS_REGION", DEFAULT_REGION)
    if bucket_name in INVALID_BUCKET_VALUES:
        logger.error(
            "TOS bucket is missing or still uses a placeholder value. Set DATABASE_TOS_BUCKET to a real bucket name."
        )
        return None

    if not os.path.exists(file_path):
        logger.error(f"File does not exist: {file_path}")
        return None
    if not os.path.isfile(file_path):
        logger.error(f"Path is not a file: {file_path}")
        return None

    try:
        from get_aksk import get_aksk

        cred = get_aksk()
        access_key = cred["access_key"]
        secret_key = cred["secret_key"]
        session_token = cred["session_token"]
    except RuntimeError as e:
        logger.error(f"Failed to get AK/SK: {e}")
        return None

    if not object_key:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem, ext = os.path.splitext(os.path.basename(file_path))
        object_key = f"upload/{stem}_{timestamp}{ext}"

    client = None
    try:
        endpoint = f"tos-{region}.volces.com"
        client = tos.TosClientV2(
            ak=access_key,
            sk=secret_key,
            security_token=session_token,
            endpoint=endpoint,
            region=region,
        )

        logger.info(f"Uploading file: {file_path} -> {bucket_name}/{object_key}")

        try:
            client.head_bucket(bucket_name)
        except tos.exceptions.TosServerError as e:
            if e.status_code == 404:
                logger.warning(f"Bucket does not exist: {bucket_name}")
            else:
                raise e

        client.put_object_from_file(
            bucket=bucket_name, key=object_key, file_path=file_path
        )

        signed_url_output = client.pre_signed_url(
            http_method=HttpMethodType.Http_Method_Get,
            bucket=bucket_name,
            key=object_key,
            expires=expires,
        )

        signed_url = signed_url_output.signed_url
        logger.info(f"Upload succeeded, signed URL: {signed_url[:100]}...")
        return signed_url

    except tos.exceptions.TosClientError as e:
        logger.error(f"TOS client error: {e}")
        return None
    except tos.exceptions.TosServerError as e:
        logger.error(f"TOS server error: {e}")
        return None
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        return None
    finally:
        if client:
            client.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
    parser = argparse.ArgumentParser(description="Upload a file to TOS")
    parser.add_argument("file_path", help="Local file path")
    parser.add_argument("--bucket", default=None, help="TOS bucket name")
    parser.add_argument("--object-key", default=None, help="Object storage path")
    parser.add_argument("--region", default=None, help="TOS region")
    parser.add_argument("--expires", type=int, default=604800, help="URL expiration in seconds")
    args = parser.parse_args()

    url = upload_file_to_tos(
        file_path=args.file_path,
        bucket_name=args.bucket,
        object_key=args.object_key,
        region=args.region,
        expires=args.expires,
    )

    if url:
        print(json.dumps({"signed_url": url}, ensure_ascii=False))
    else:
        print(json.dumps({"error": "Upload failed"}, ensure_ascii=False))
        sys.exit(1)
