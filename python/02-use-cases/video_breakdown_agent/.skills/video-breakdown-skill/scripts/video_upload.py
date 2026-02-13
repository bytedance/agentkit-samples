"""
上传本地视频文件到火山引擎 TOS 对象存储，返回签名 URL。

Usage:
    python scripts/video_upload.py "<file_path>" [bucket_name]

Examples:
    python scripts/video_upload.py "/path/to/video.mp4"
    python scripts/video_upload.py "/path/to/video.mp4" "my-bucket"
"""

import json
import os
import sys
from datetime import datetime

import tos
from tos import HttpMethodType

DEFAULT_BUCKET = "video-breakdown-uploads"
DEFAULT_REGION = "cn-beijing"


def video_upload_to_tos(file_path: str, bucket_name: str = None) -> dict:
    """
    将本地视频文件上传到 TOS，返回签名 URL。

    Args:
        file_path: 本地视频文件路径
        bucket_name: TOS 存储桶名称（可选）

    Returns:
        dict: 包含 video_url 或 error
    """
    if bucket_name is None:
        bucket_name = os.getenv("DATABASE_TOS_BUCKET") or os.getenv(
            "TOS_BUCKET", DEFAULT_BUCKET
        )
    region = os.getenv("DATABASE_TOS_REGION") or os.getenv("TOS_REGION", DEFAULT_REGION)

    # 检查文件
    if not os.path.exists(file_path):
        return {"error": f"文件不存在: {file_path}"}
    if not os.path.isfile(file_path):
        return {"error": f"路径不是文件: {file_path}"}

    file_size = os.path.getsize(file_path)
    max_size = 2 * 1024 * 1024 * 1024  # 2GB
    if file_size > max_size:
        return {"error": f"文件过大（{file_size / 1024 / 1024:.0f}MB），最大支持 2GB"}

    # 获取凭证
    access_key = os.getenv("VOLCENGINE_ACCESS_KEY", "")
    secret_key = os.getenv("VOLCENGINE_SECRET_KEY", "")
    session_token = ""

    if not access_key or not secret_key:
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
            "error": "缺少 TOS 访问凭证，请设置 VOLCENGINE_ACCESS_KEY 和 VOLCENGINE_SECRET_KEY"
        }

    # 自动生成 object_key
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.basename(file_path)
    object_key = f"video_breakdown/upload/{timestamp}_{filename}"

    # 上传
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

        # 检查桶
        try:
            client.head_bucket(bucket_name)
        except tos.exceptions.TosServerError as e:
            if e.status_code == 404:
                return {"error": f"TOS 存储桶 {bucket_name} 不存在"}
            raise

        print(f"上传中: {file_path} -> {bucket_name}/{object_key}", file=sys.stderr)
        client.put_object_from_file(
            bucket=bucket_name, key=object_key, file_path=file_path
        )

        # 生成签名 URL（7天有效）
        signed_url_output = client.pre_signed_url(
            http_method=HttpMethodType.Http_Method_Get,
            bucket=bucket_name,
            key=object_key,
            expires=604800,
        )

        return {
            "video_url": signed_url_output.signed_url,
            "bucket": bucket_name,
            "object_key": object_key,
            "file_size_mb": round(file_size / 1024 / 1024, 2),
            "message": "上传成功！使用 video_url 调用 process_video.py 进行视频分镜分析",
        }

    except tos.exceptions.TosClientError as e:
        return {"error": f"TOS 客户端错误: {e}"}
    except tos.exceptions.TosServerError as e:
        return {"error": f"TOS 服务端错误: {e.message}"}
    except Exception as e:
        return {"error": f"上传失败: {str(e)}"}
    finally:
        if client:
            client.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python video_upload.py <file_path> [bucket_name]")
        sys.exit(1)

    path = sys.argv[1]
    bucket = sys.argv[2] if len(sys.argv) > 2 else None
    result = video_upload_to_tos(path, bucket)
    print(json.dumps(result, ensure_ascii=False, indent=2))
