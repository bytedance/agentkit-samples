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

logger = logging.getLogger(__name__)

# 默认常量
DEFAULT_BUCKET = "agentkit-platform-2107625663"
DEFAULT_REGION = "cn-beijing"


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

    if not os.path.exists(file_path):
        logger.error(f"文件不存在: {file_path}")
        return None
    if not os.path.isfile(file_path):
        logger.error(f"路径不是文件: {file_path}")
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
        filename = os.path.basename(file_path)
        object_key = f"upload/{filename}_{timestamp}"

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

        logger.info(f"上传文件: {file_path} -> {bucket_name}/{object_key}")

        try:
            client.head_bucket(bucket_name)
        except tos.exceptions.TosServerError as e:
            if e.status_code == 404:
                logger.warning(f"桶 {bucket_name} 不存在")
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
        logger.info(f"上传成功，签名 URL: {signed_url[:100]}...")
        return signed_url

    except tos.exceptions.TosClientError as e:
        logger.error(f"TOS 客户端错误: {e}")
        return None
    except tos.exceptions.TosServerError as e:
        logger.error(f"TOS 服务端错误: {e}")
        return None
    except Exception as e:
        logger.error(f"上传失败: {e}")
        return None
    finally:
        if client:
            client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="上传文件到 TOS")
    parser.add_argument("file_path", help="本地文件路径")
    parser.add_argument("--bucket", default=None, help="TOS 桶名")
    parser.add_argument("--object-key", default=None, help="存储路径")
    parser.add_argument("--region", default=None, help="区域")
    parser.add_argument("--expires", type=int, default=604800, help="URL 有效期（秒）")
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
        print(json.dumps({"error": "上传失败"}, ensure_ascii=False))
        sys.exit(1)
