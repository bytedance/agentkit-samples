"""
Doubao-Seedance视频生成API调用工具
参考: multimedia/director-agent/src/director_agent/tools/video_generate_http.py

默认模型：Doubao-Seedance-1.5-pro
要求：必须配置 MODEL_VIDEO_API_KEY 环境变量
"""

from __future__ import annotations

import asyncio
import base64
import logging
import uuid
from typing import Dict, List, Optional

import aiohttp
from google.adk.tools import ToolContext
from veadk.config import getenv, settings
from veadk.consts import DEFAULT_VIDEO_MODEL_API_BASE

logger = logging.getLogger(__name__)

# 默认视频生成模型（按场景区分）
# I2V（图生视频）：doubao-seedance-1-5-pro-251215，支持首尾帧、有声视频、adaptive比例
# T2V（文生视频）：doubao-seedance-1-0-pro-250528，纯文本生成
# Lite（轻量图生视频）：doubao-seedance-1-0-lite-i2v-250428，参考图
DEFAULT_VIDEO_MODEL = "doubao-seedance-1-5-pro-251215"  # i2v 默认
DEFAULT_VIDEO_MODEL_T2V = "doubao-seedance-1-0-pro-250528"  # t2v 默认

# Doubao-Seedance 系列合法时长（秒），超出范围自动 snap 到最近合法值
_VALID_DURATIONS = [5, 10]


def _snap_duration(raw: int) -> int:
    """将任意时长 snap 到最近的合法值（5 或 10 秒）"""
    return min(_VALID_DURATIONS, key=lambda v: abs(v - raw))


def _is_base64_data_url(url: str) -> bool:
    """检查 URL 是否为 base64 data URL"""
    return isinstance(url, str) and url.startswith("data:image/")


async def _upload_base64_to_tos(base64_url: str) -> Optional[str]:
    """
    将 base64 data URL 上传到 TOS 并返回公开 URL

    Args:
        base64_url: base64 data URL (格式: data:image/jpeg;base64,...)

    Returns:
        公开的 TOS URL，如果上传失败返回 None
    """
    try:
        # 解析 base64 data URL
        if not base64_url.startswith("data:image/"):
            return None

        # 提取 MIME 类型和 base64 数据
        header, data = base64_url.split(",", 1)
        mime_type = header.split(":")[1].split(";")[0]  # 提取 image/jpeg

        # 解码 base64
        image_bytes = base64.b64decode(data)

        # 获取 TOS 凭证
        try:
            import tos
            from tos import HttpMethodType
        except ImportError:
            logger.warning("[_upload_base64_to_tos] tos 库未安装，无法上传 base64 图片")
            return None

        ak = getenv("VOLCENGINE_ACCESS_KEY", "")
        sk = getenv("VOLCENGINE_SECRET_KEY", "")

        if not ak or not sk:
            try:
                from veadk.auth.veauth.utils import get_credential_from_vefaas_iam

                cred = get_credential_from_vefaas_iam()
                ak = cred.access_key_id
                sk = cred.secret_access_key
            except Exception:
                logger.warning("[_upload_base64_to_tos] 无法获取 TOS 凭证")
                return None

        if not ak or not sk:
            logger.warning("[_upload_base64_to_tos] TOS 凭证未配置")
            return None

        bucket = getenv("DATABASE_TOS_BUCKET") or getenv(
            "TOS_BUCKET", "video-breakdown-uploads"
        )
        region = getenv("DATABASE_TOS_REGION") or getenv("TOS_REGION", "cn-beijing")
        endpoint = f"tos-{region}.volces.com"

        # 生成 object key
        ext = ".jpg" if "jpeg" in mime_type else ".png"
        object_key = f"video_breakdown/frames/{uuid.uuid4().hex[:8]}{ext}"

        # 上传到 TOS
        client = tos.TosClientV2(ak=ak, sk=sk, endpoint=endpoint, region=region)
        try:
            await asyncio.to_thread(
                client.put_object,
                bucket=bucket,
                key=object_key,
                content=image_bytes,
                content_type=mime_type,
            )

            # 生成签名 URL
            signed = await asyncio.to_thread(
                client.pre_signed_url,
                http_method=HttpMethodType.Http_Method_Get,
                bucket=bucket,
                key=object_key,
                expires=604800,  # 7 天
            )

            logger.info(
                f"[_upload_base64_to_tos] base64 图片已上传到 TOS: {object_key}"
            )
            return signed.signed_url
        finally:
            client.close()

    except Exception as exc:
        logger.warning(f"[_upload_base64_to_tos] 上传失败: {exc}")
        return None


def validate_video_model_config() -> tuple[bool, str]:
    """
    验证视频生成模型配置

    Returns:
        (is_valid, error_message)
    """
    # 检查API Key
    api_key = getenv(
        "MODEL_VIDEO_API_KEY", getenv("MODEL_AGENT_API_KEY", settings.model.api_key)
    )

    if not api_key:
        return False, (
            "❌ 视频生成模型未配置！\n\n"
            "请配置以下环境变量之一：\n"
            "1. MODEL_VIDEO_API_KEY（推荐，专用于视频生成）\n"
            "2. MODEL_AGENT_API_KEY（通用API Key）\n\n"
            "示例配置：\n"
            "export MODEL_VIDEO_API_KEY='your_api_key_here'\n\n"
            "💡 提示：视频生成功能需要 Doubao-Seedance 模型权限\n"
            "  支持的模型：\n"
            "  - doubao-seedance-1-5-pro-251215 (推荐，支持首尾帧/音频)\n"
            "  - doubao-seedance-1-0-pro-250528 (标准版)\n"
            "  - doubao-seedance-1-0-lite-i2v-250428 (图生视频)"
        )

    # 检查Base URL
    base_url = getenv("MODEL_VIDEO_API_BASE", DEFAULT_VIDEO_MODEL_API_BASE)
    if not base_url:
        return False, (
            "❌ 视频生成API Base URL未配置！\n\n"
            "请配置环境变量：\n"
            "export MODEL_VIDEO_API_BASE='https://ark.cn-beijing.volces.com/api/v3'\n"
        )

    # 获取模型名称（使用默认值）
    model = getenv("MODEL_VIDEO_NAME", DEFAULT_VIDEO_MODEL)

    logger.info(f"✅ 视频生成模型配置验证通过：{model}")
    return True, ""


async def generate_single_video(
    prompt: str,
    first_frame_image: Optional[str] = None,
    last_frame_image: Optional[str] = None,
    reference_images: Optional[List[str]] = None,
    duration: int = 5,
    ratio: str = "9:16",
    generate_audio: bool = False,
    **kwargs,
) -> Dict:
    """
    生成单个视频片段（支持多种图片输入格式）

    Args:
        prompt: 视频生成提示词
        first_frame_image: 首帧图片URL（可选）
        last_frame_image: 尾帧图片URL（可选，仅1.5-pro支持）
        reference_images: 参考图片URL列表（可选，lite版支持）
        duration: 视频时长（秒，整数）
        ratio: 宽高比（16:9/9:16/1:1/adaptive）
        generate_audio: 是否生成音频（仅1.5-pro支持）

    Returns:
        API响应: {"id": "task_id", "status": "processing"}
    """
    api_key = getenv(
        "MODEL_VIDEO_API_KEY", getenv("MODEL_AGENT_API_KEY", settings.model.api_key)
    )
    base_url = getenv("MODEL_VIDEO_API_BASE", DEFAULT_VIDEO_MODEL_API_BASE)
    # 模型先用用户配置值，稍后根据是否有图片自动选择 t2v/i2v 默认值
    configured_model = getenv("MODEL_VIDEO_NAME", "")

    # 构建请求内容（按官方格式）
    content = [{"type": "text", "text": prompt}]

    # 处理首帧图片（如果提供）
    if first_frame_image:
        # 如果是 base64 data URL，先上传到 TOS
        if _is_base64_data_url(first_frame_image):
            logger.info(
                "[generate_single_video] 检测到 base64 首帧图片，正在上传到 TOS..."
            )
            first_frame_image = await _upload_base64_to_tos(first_frame_image)
            if not first_frame_image:
                logger.warning(
                    "[generate_single_video] base64 首帧图片上传失败，将跳过首帧图片"
                )
            else:
                logger.info("[generate_single_video] base64 首帧图片已转换为公开 URL")

        if first_frame_image:  # 只有成功转换或原本就是公开 URL 才添加
            img_item = {
                "type": "image_url",
                "image_url": {"url": first_frame_image},
            }
            # 仅首尾帧模式（同时有 last_frame_image）才加 role 字段
            # 单图模式（图生视频）不能发送 "role": null，API 会报错
            if last_frame_image:
                img_item["role"] = "first_frame"
            content.append(img_item)

    # 处理尾帧图片（仅1.5-pro支持）
    if last_frame_image:
        # 如果是 base64 data URL，先上传到 TOS
        if _is_base64_data_url(last_frame_image):
            logger.info(
                "[generate_single_video] 检测到 base64 尾帧图片，正在上传到 TOS..."
            )
            last_frame_image = await _upload_base64_to_tos(last_frame_image)
            if not last_frame_image:
                logger.warning(
                    "[generate_single_video] base64 尾帧图片上传失败，将跳过尾帧图片"
                )
            else:
                logger.info("[generate_single_video] base64 尾帧图片已转换为公开 URL")

        if last_frame_image:  # 只有成功转换或原本就是公开 URL 才添加
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": last_frame_image},
                    "role": "last_frame",
                }
            )

    # 处理参考图片（lite版支持）
    if reference_images:
        valid_ref_images = []
        for ref_img in reference_images:
            # 如果是 base64 data URL，先上传到 TOS
            if _is_base64_data_url(ref_img):
                logger.info(
                    "[generate_single_video] 检测到 base64 参考图片，正在上传到 TOS..."
                )
                ref_img = await _upload_base64_to_tos(ref_img)
                if not ref_img:
                    logger.warning(
                        "[generate_single_video] base64 参考图片上传失败，将跳过该图片"
                    )
                    continue
                else:
                    logger.info(
                        "[generate_single_video] base64 参考图片已转换为公开 URL"
                    )

            if ref_img:  # 只有成功转换或原本就是公开 URL 才添加
                valid_ref_images.append(ref_img)

        # 添加有效的参考图片
        for ref_img in valid_ref_images:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": ref_img},
                    "role": "reference_image",
                }
            )

    # Doubao-Seedance 系列模型只接受 5 或 10 秒两个合法时长，自动 snap
    raw_duration = int(duration)
    valid_duration = _snap_duration(raw_duration)
    if valid_duration != raw_duration:
        logger.info(
            f"[generate_single_video] 时长 {raw_duration}s 不被 API 支持，"
            f"已自动调整为 {valid_duration}s（合法值：5 或 10）"
        )

    # 根据是否有图片内容自动选择模型
    # - 有图片 (i2v)：优先 doubao-seedance-1-5-pro-251215
    # - 纯文本 (t2v)：优先 doubao-seedance-1-0-pro-250528
    has_image = any(item.get("type") == "image_url" for item in content)
    if configured_model:
        model = configured_model
    elif has_image:
        model = DEFAULT_VIDEO_MODEL  # 1.5-pro，i2v 默认
    else:
        model = DEFAULT_VIDEO_MODEL_T2V  # 1.0-pro，t2v 默认

    logger.info(
        f"[generate_single_video] 模式={'i2v' if has_image else 't2v'}, "
        f"模型={model}, 原始时长={int(duration)}s → {valid_duration}s, "
        f"比例={ratio}, 音频={generate_audio}"
    )

    # 构建请求体（参考官方API格式）
    request_body = {
        "model": model,
        "content": content,
        "ratio": ratio,
        "duration": valid_duration,
        "watermark": False,
    }

    # 如果启用音频生成（仅1.5-pro支持）
    if generate_audio and "1-5-pro" in model:
        request_body["generate_audio"] = True

    # 发送请求
    async with aiohttp.ClientSession() as session:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        async with session.post(
            f"{base_url.rstrip('/')}/contents/generations/tasks",
            json=request_body,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as response:
            # 改进错误处理，提供更详细的错误信息
            if response.status != 200:
                # 先尝试解析 JSON 错误信息
                error_msg = None
                try:
                    error_json = await response.json()
                    error_msg = error_json.get("error", {}).get(
                        "message"
                    ) or error_json.get("message")
                except Exception:
                    # 如果 JSON 解析失败，读取文本
                    try:
                        error_text = await response.text()
                        error_msg = (
                            error_text[:500]
                            if error_text
                            else f"HTTP {response.status}"
                        )
                    except Exception:
                        error_msg = f"HTTP {response.status}"

                logger.error(
                    f"视频生成请求失败: HTTP {response.status}, 错误信息: {error_msg}"
                )

                raise aiohttp.ClientResponseError(
                    request_info=response.request_info,
                    history=response.history,
                    status=response.status,
                    message=f"请求无效（Bad Request）: {error_msg}。"
                    f"可能是参考图片无法访问或提示词格式问题，"
                    f"请检查参考图片是否为公开可访问的链接，或调整提示词后重试。",
                )

            result = await response.json()
            logger.info(f"视频生成任务已提交: task_id={result.get('id')}")
            return result


async def poll_task_status(
    task_id: str,
    max_wait_time: int = 600,  # 最大等待10分钟
    poll_interval: int = 10,  # 每10秒轮询一次
) -> Dict:
    """
    轮询任务状态直到完成

    Args:
        task_id: 任务ID
        max_wait_time: 最大等待时间（秒）
        poll_interval: 轮询间隔（秒）

    Returns:
        任务结果: {"status": "succeeded/failed", "video_url": "..."}
    """
    api_key = getenv(
        "MODEL_VIDEO_API_KEY", getenv("MODEL_AGENT_API_KEY", settings.model.api_key)
    )
    base_url = getenv("MODEL_VIDEO_API_BASE", DEFAULT_VIDEO_MODEL_API_BASE)

    elapsed_time = 0

    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        while elapsed_time < max_wait_time:
            try:
                async with session.get(
                    f"{base_url.rstrip('/')}/contents/generations/tasks/{task_id}",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
                    status = result.get("status")

                    if status == "succeeded":
                        video_url = result.get("content", {}).get("video_url")
                        logger.info(f"任务{task_id}生成成功: {video_url}")
                        return {
                            "status": "succeeded",
                            "video_url": video_url,
                            "task_id": task_id,
                        }

                    elif status == "failed":
                        error_msg = result.get("error", "Unknown error")
                        logger.error(f"任务{task_id}生成失败: {error_msg}")
                        return {
                            "status": "failed",
                            "error": error_msg,
                            "task_id": task_id,
                        }

                    else:
                        # 仍在处理中
                        logger.debug(
                            f"任务{task_id}当前状态: {status}, 已等待{elapsed_time}s"
                        )

            except Exception as e:
                logger.warning(f"查询任务{task_id}状态失败: {e}")

            # 等待后再次轮询
            await asyncio.sleep(poll_interval)
            elapsed_time += poll_interval

        # 超时
        logger.error(f"任务{task_id}超时（{max_wait_time}s）")
        return {
            "status": "timeout",
            "error": f"任务超时（超过{max_wait_time}秒）",
            "task_id": task_id,
        }


async def video_generate(
    tool_context: ToolContext,
    batch_size: int = 3,  # 限制并发数
) -> Dict:
    """
    批量生成视频工具（仅生成用户选中的分镜）

    参考: multimedia/director-agent/src/director_agent/tools/video_generate_http.py

    从session.state读取pending_prompts，仅生成selected=True的分镜。
    使用Semaphore限制并发数，避免API限流。

    Args:
        tool_context: 工具上下文
        batch_size: 最大并发生成数（默认3）

    Returns:
        {
            "status": "success" | "error" | "partial",
            "success_list": [{"segment_1": "video_url"}],
            "error_list": [{"segment_2": "error_msg"}],
            "total_requested": int,
            "total_succeeded": int,
            "total_failed": int,
            "message": str
        }
    """
    try:
        logger.info("=" * 60)
        logger.info("🎬 开始视频生成流程")
        logger.info("=" * 60)

        # ⭐ 强制配置验证
        is_valid, error_msg = validate_video_model_config()
        if not is_valid:
            logger.error("❌ 视频生成模型配置验证失败")
            return {
                "status": "error",
                "message": error_msg,
                "success_list": [],
                "error_list": [],
                "total_requested": 0,
                "total_succeeded": 0,
                "total_failed": 0,
            }

        # 读取待生成的提示词
        pending_prompts = tool_context.state.get("pending_prompts")

        if not pending_prompts:
            logger.error("❌ 未找到 pending_prompts，请先准备提示词")
            return {
                "status": "error",
                "message": "未找到待生成的提示词，请先生成并审核提示词",
                "success_list": [],
                "error_list": [],
                "total_requested": 0,
                "total_succeeded": 0,
                "total_failed": 0,
            }

        prompts = pending_prompts.get("prompts", [])

        # 筛选出选中的分镜
        selected_prompts = [p for p in prompts if p.get("selected", False)]

        if not selected_prompts:
            logger.error("❌ 没有选中任何分镜")
            return {
                "status": "error",
                "message": "没有选中任何分镜，请至少选择一个分镜生成",
                "success_list": [],
                "error_list": [],
                "total_requested": 0,
                "total_succeeded": 0,
                "total_failed": 0,
            }

        # 获取配置的模型名称
        model_name = getenv("MODEL_VIDEO_NAME", DEFAULT_VIDEO_MODEL)
        logger.info(f"📋 待生成分镜数量: {len(selected_prompts)}, 模型: {model_name}")
        for p in selected_prompts:
            logger.info(
                f"  - {p.get('segment_name', 'unknown')}: {p.get('duration', 5)}秒, 提示词长度={len(p.get('positive_prompt', ''))}"
            )

        success_list = []
        error_list = []
        task_dict = {}  # task_id: segment_info

        # 第1步：批量提交任务（使用Semaphore限流）
        semaphore = asyncio.Semaphore(batch_size)

        async def submit_task(prompt_data):
            async with semaphore:
                segment_index = prompt_data["segment_index"]
                segment_name = prompt_data["segment_name"]

                try:
                    response = await generate_single_video(
                        prompt=prompt_data["positive_prompt"],
                        first_frame_image=prompt_data.get("first_frame"),
                        last_frame_image=prompt_data.get("last_frame"),
                        reference_images=prompt_data.get("reference_images"),
                        duration=int(prompt_data.get("duration", 5)),
                        ratio=prompt_data.get("ratio", "9:16"),
                        generate_audio=prompt_data.get("generate_audio", False),
                    )

                    task_id = response["id"]
                    task_dict[task_id] = {
                        "segment_name": segment_name,
                        "segment_index": segment_index,
                        "prompt_data": prompt_data,
                    }
                    logger.info(f"分镜{segment_index}任务已提交: {task_id}")

                except Exception as e:
                    logger.error(f"分镜{segment_index}提交失败: {e}")
                    error_list.append({"segment_name": segment_name, "error": str(e)})

        await asyncio.gather(
            *[submit_task(item) for item in selected_prompts], return_exceptions=True
        )

        logger.info(f"📤 任务提交完成: 成功{len(task_dict)}个, 失败{len(error_list)}个")

        # 第2步：轮询任务状态（并发轮询）
        logger.info(
            f"⏳ 开始轮询任务状态（共{len(task_dict)}个任务，每10秒查询，最多10分钟）..."
        )

        async def poll_single_task(task_id, segment_info):
            result = await poll_task_status(task_id)

            if result["status"] == "succeeded":
                video_url = result["video_url"]
                segment_name = segment_info["segment_name"]

                # 存入session state
                tool_context.state[f"{segment_name}_video_url"] = video_url

                success_list.append(
                    {
                        segment_name: video_url,
                        "segment_index": segment_info["segment_index"],
                    }
                )
                logger.info(f"✅ {segment_name}生成成功")
            else:
                error_msg = result.get("error", "Unknown error")
                error_list.append(
                    {"segment_name": segment_info["segment_name"], "error": error_msg}
                )
                logger.error(f"❌ {segment_info['segment_name']}生成失败: {error_msg}")

        await asyncio.gather(
            *[poll_single_task(tid, info) for tid, info in task_dict.items()],
            return_exceptions=True,
        )

        # 统计结果
        total_requested = len(selected_prompts)
        total_succeeded = len(success_list)
        total_failed = len(error_list)

        # 存储生成结果到session state（带数据验证）
        if not isinstance(success_list, list):
            logger.error(
                f"⚠️ success_list 格式异常: {type(success_list)}，已重置为空列表"
            )
            success_list = []

        # 确保每个元素都是字典
        validated_list = [item for item in success_list if isinstance(item, dict)]
        if len(validated_list) != len(success_list):
            logger.warning(
                f"⚠️ success_list 中有 {len(success_list) - len(validated_list)} 个非字典元素被过滤"
            )

        tool_context.state["generated_videos"] = validated_list
        logger.info(
            f"📦 存储 generated_videos: {len(validated_list)} 个分镜, 数据类型: {[type(x).__name__ for x in validated_list]}"
        )

        # 判断最终状态
        if total_succeeded == total_requested:
            final_status = "success"
            message = f"✅ 所有{total_requested}个分镜生成成功"
        elif total_succeeded > 0:
            final_status = "partial"
            message = f"⚠️ 部分成功：{total_succeeded}/{total_requested}个分镜生成成功，{total_failed}个失败"
        else:
            final_status = "error"
            message = "❌ 所有分镜生成失败"

        logger.info("=" * 60)
        logger.info(f"🎉 视频生成完成: {message}")
        for item in success_list:
            for key, value in item.items():
                if key not in ("segment_index",):
                    logger.info(f"  ✅ {key}: {value}")
        for item in error_list:
            logger.info(
                f"  ❌ {item.get('segment_name', 'unknown')}: {item.get('error', 'Unknown')}"
            )
        logger.info("=" * 60)

        # 清除已完成的 pending_prompts，防止意外重复调用
        for p in prompts:
            p["selected"] = False
        tool_context.state["pending_prompts"] = pending_prompts

        return {
            "status": final_status,
            "success_list": success_list,
            "error_list": error_list,
            "total_requested": total_requested,
            "total_succeeded": total_succeeded,
            "total_failed": total_failed,
            "message": message,
        }

    except Exception as e:
        logger.error(f"视频生成失败: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"视频生成失败: {str(e)}",
            "success_list": [],
            "error_list": [],
            "total_requested": 0,
            "total_succeeded": 0,
            "total_failed": 0,
        }
