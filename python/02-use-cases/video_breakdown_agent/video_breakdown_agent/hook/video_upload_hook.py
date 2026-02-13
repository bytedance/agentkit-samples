"""
视频文件上传钩子（before_agent_callback）

当用户通过 veadk web UI 上传视频文件时，ADK 将文件二进制数据
以 Part.inline_data 传入。LLM 无法处理原始二进制，会导致
工具调用 JSON 生成失败（Unterminated string）。

此钩子在 Agent 处理之前拦截 inline_data：
  1. 保存到临时文件
  2. 尝试上传到 TOS 获取签名 URL
  3. 如果 TOS 不可用，保留本地文件路径
  4. 将 inline_data Part 替换为文本 Part

参考实现: ad_video_gen_seq/app/market/hook.py → hook_inline_data_transform
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.genai import types

logger = logging.getLogger(__name__)

# 支持的视频 MIME 类型
VIDEO_MIME_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/x-msvideo",
    "video/webm",
    "video/x-matroska",
    "video/mpeg",
    "video/3gpp",
    "video/x-flv",
    "application/octet-stream",  # 某些浏览器上传时 MIME 可能不精确
}

# 持久化目录（不会被 process_video 的 finally 清理）
UPLOAD_CACHE_DIR = os.getenv("MEDIA_UPLOAD_CACHE_DIR", "./.media-uploads")


def _try_upload_to_tos(local_path: str) -> Optional[str]:
    """尝试将文件上传到 TOS，成功返回签名 URL，失败返回 None"""
    try:
        import tos
        from tos import HttpMethodType

        ak = os.getenv("VOLCENGINE_ACCESS_KEY", "")
        sk = os.getenv("VOLCENGINE_SECRET_KEY", "")

        if not ak or not sk:
            try:
                from veadk.auth.veauth.utils import get_credential_from_vefaas_iam

                cred = get_credential_from_vefaas_iam()
                ak = cred.access_key_id
                sk = cred.secret_access_key
            except Exception:
                return None

        if not ak or not sk:
            return None

        bucket = os.getenv("DATABASE_TOS_BUCKET") or os.getenv(
            "TOS_BUCKET", "video-breakdown-uploads"
        )
        region = os.getenv("DATABASE_TOS_REGION") or os.getenv(
            "TOS_REGION", "cn-beijing"
        )
        endpoint = f"tos-{region}.volces.com"

        client = tos.TosClientV2(ak=ak, sk=sk, endpoint=endpoint, region=region)
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.basename(local_path)
            object_key = f"video_breakdown/upload/{timestamp}_{filename}"

            client.put_object_from_file(
                bucket=bucket, key=object_key, file_path=local_path
            )

            signed = client.pre_signed_url(
                http_method=HttpMethodType.Http_Method_Get,
                bucket=bucket,
                key=object_key,
                expires=604800,  # 7 天
            )
            logger.info(f"[video_upload_hook] 文件已上传到 TOS: {object_key}")
            return signed.signed_url
        finally:
            client.close()

    except Exception as exc:
        logger.warning(f"[video_upload_hook] TOS 上传失败，回退到本地路径: {exc}")
        return None


def hook_video_upload(
    callback_context: CallbackContext,
) -> Optional[types.Content]:
    """
    before_agent_callback：拦截用户消息中的 inline_data（上传文件），
    转换为文本 URL 或本地路径，确保 LLM 不接触原始二进制数据。
    """
    user_content = callback_context.user_content
    if not user_content or not user_content.parts:
        return None

    new_parts = []
    has_inline_data = False

    for part in user_content.parts:
        # 保留文本 Part
        if part.text:
            new_parts.append(types.Part(text=part.text))

        # 处理 inline_data（上传的文件）
        if part.inline_data and part.inline_data.data:
            has_inline_data = True
            mime_type = part.inline_data.mime_type or "application/octet-stream"
            data = part.inline_data.data

            logger.info(
                f"[video_upload_hook] 检测到 inline_data: "
                f"mime={mime_type}, size={len(data)} bytes"
            )

            # 根据 MIME 类型确定文件后缀
            ext = _mime_to_ext(mime_type)

            # 保存到持久化目录（不受 process_video 临时目录清理影响）
            upload_dir = Path(UPLOAD_CACHE_DIR)
            upload_dir.mkdir(parents=True, exist_ok=True)

            filename = f"upload_{uuid.uuid4().hex[:8]}{ext}"
            local_path = upload_dir / filename

            with open(local_path, "wb") as f:
                f.write(data)

            logger.info(
                f"[video_upload_hook] 文件已保存: {local_path} "
                f"({len(data) / 1024 / 1024:.1f}MB)"
            )

            # 尝试上传到 TOS
            tos_url = _try_upload_to_tos(str(local_path))

            if tos_url:
                new_parts.append(types.Part(text=f"用户上传了视频文件，URL: {tos_url}"))
                # TOS 上传成功后可以删除本地文件
                try:
                    local_path.unlink()
                except Exception:
                    pass
            else:
                # TOS 不可用，使用本地路径
                abs_path = str(local_path.resolve())
                new_parts.append(
                    types.Part(text=f"用户上传了视频文件，本地路径: {abs_path}")
                )

    if has_inline_data:
        user_content.parts = new_parts
        logger.info(
            f"[video_upload_hook] inline_data 已转换为文本 ({len(new_parts)} parts)"
        )

    # 返回 None 表示不中断正常流程
    return None


def _mime_to_ext(mime_type: str) -> str:
    """将 MIME 类型映射为文件扩展名"""
    mapping = {
        "video/mp4": ".mp4",
        "video/quicktime": ".mov",
        "video/x-msvideo": ".avi",
        "video/webm": ".webm",
        "video/x-matroska": ".mkv",
        "video/mpeg": ".mpeg",
        "video/3gpp": ".3gp",
        "video/x-flv": ".flv",
        "audio/mpeg": ".mp3",
        "audio/wav": ".wav",
        "audio/mp4": ".m4a",
    }
    return mapping.get(mime_type, ".mp4")  # 默认 .mp4
