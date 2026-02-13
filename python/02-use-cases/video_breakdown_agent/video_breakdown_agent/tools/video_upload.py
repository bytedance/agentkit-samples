"""
视频文件上传到 TOS 对象存储工具
基于 inspection_assistant/tools/tos_upload.py 模式实现
"""

import logging
import os
from datetime import datetime
from typing import Optional

import tos
from tos import HttpMethodType

logger = logging.getLogger(__name__)

DEFAULT_BUCKET = "video-breakdown-uploads"
DEFAULT_REGION = "cn-beijing"


def video_upload_to_tos(
    file_path: str,
    bucket_name: Optional[str] = None,
    object_key: Optional[str] = None,
) -> dict:
    """
    将本地视频文件上传到火山引擎 TOS 对象存储，并返回可访问的签名 URL。
    上传成功后，返回的 URL 可直接用于 process_video 工具进行视频分镜分析。

    Args:
        file_path: 本地视频文件路径，例如 /path/to/video.mp4
        bucket_name: TOS 存储桶名称（可选，默认从配置读取）
        object_key: 对象存储路径（可选，默认自动生成）

    Returns:
        dict: 包含 video_url（签名URL）和上传信息，或 error 信息
    """
    # 从环境变量/config.yaml 读取配置（VeADK 扁平化: DATABASE_TOS_*，兼容旧: TOS_*）
    if bucket_name is None:
        bucket_name = os.getenv("DATABASE_TOS_BUCKET") or os.getenv(
            "TOS_BUCKET", DEFAULT_BUCKET
        )
    region = os.getenv("DATABASE_TOS_REGION") or os.getenv("TOS_REGION", DEFAULT_REGION)

    # 检查文件是否存在
    if not os.path.exists(file_path):
        return {"error": f"文件不存在: {file_path}"}

    if not os.path.isfile(file_path):
        return {"error": f"路径不是文件: {file_path}"}

    # 检查文件大小（限制 2GB）
    file_size = os.path.getsize(file_path)
    max_size = 2 * 1024 * 1024 * 1024  # 2GB
    if file_size > max_size:
        return {"error": f"文件过大（{file_size / 1024 / 1024:.0f}MB），最大支持 2GB"}

    # 获取凭证：优先从配置/环境变量，其次从 VeFaaS IAM
    access_key = os.getenv("VOLCENGINE_ACCESS_KEY", "")
    secret_key = os.getenv("VOLCENGINE_SECRET_KEY", "")
    session_token = ""

    if not (access_key and secret_key):
        try:
            from veadk.auth.veauth.utils import get_credential_from_vefaas_iam

            cred = get_credential_from_vefaas_iam()
            access_key = cred.access_key_id
            secret_key = cred.secret_access_key
            session_token = cred.session_token
        except Exception:
            pass

    if not access_key or not secret_key:
        return {
            "error": "缺少 TOS 访问凭证。请设置 VOLCENGINE_ACCESS_KEY 和 VOLCENGINE_SECRET_KEY 环境变量（或在 config.yaml 中配置 volcengine.access_key / volcengine.secret_key）"
        }

    # 自动生成 object_key
    if not object_key:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.basename(file_path)
        object_key = f"video_breakdown/upload/{timestamp}_{filename}"

    # 上传文件
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

        logger.info(f"开始上传视频: {file_path}")
        logger.info(f"目标桶: {bucket_name}, 对象键: {object_key}")

        # 检查桶是否存在
        try:
            client.head_bucket(bucket_name)
        except tos.exceptions.TosServerError as e:
            if e.status_code == 404:
                return {"error": f"TOS 存储桶 {bucket_name} 不存在，请先创建"}
            raise

        # 上传
        result = client.put_object_from_file(
            bucket=bucket_name, key=object_key, file_path=file_path
        )

        logger.info(f"上传成功! ETag: {result.etag}")

        # 生成签名 URL（7天有效）
        signed_url_output = client.pre_signed_url(
            http_method=HttpMethodType.Http_Method_Get,
            bucket=bucket_name,
            key=object_key,
            expires=604800,
        )

        signed_url = signed_url_output.signed_url
        logger.info("签名 URL 生成成功（7天有效）")

        return {
            "video_url": signed_url,
            "bucket": bucket_name,
            "object_key": object_key,
            "file_size_mb": round(file_size / 1024 / 1024, 2),
            "message": "视频上传成功！可以使用返回的 video_url 调用 process_video 进行分镜预处理",
        }

    except tos.exceptions.TosClientError as e:
        logger.error(f"TOS 客户端错误: {e}")
        return {"error": f"TOS 客户端错误: {e}"}
    except tos.exceptions.TosServerError as e:
        logger.error(f"TOS 服务端错误: code={e.code}, message={e.message}")
        return {"error": f"TOS 服务端错误: {e.message}"}
    except Exception as e:
        logger.error(f"上传失败: {e}")
        return {"error": f"视频上传失败: {str(e)}"}
    finally:
        if client:
            client.close()
