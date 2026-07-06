# Copyright (c) 2026 BytePlus. All rights reserved.
# SPDX-License-Identifier: Proprietary
from __future__ import annotations

from typing import Any

import httpx

from setup_links import (
    MODELARK_API_KEY_URL,
    MODEL_OPEN_MANAGEMENT_URL,
    SEEDANCE_RESOURCE_PACKAGE_URL,
    SEEDANCE_TUTORIAL_URL,
    VIDEO_GENERATION_API_URL,
)


def _short_body(response: httpx.Response) -> str:
    try:
        body: Any = response.json()
    except ValueError:
        body = response.text
    text = str(body)
    return text[:1000]


def format_provider_http_error(exc: httpx.HTTPStatusError, *, provider: str, language: str = "zh") -> str:
    response = exc.response
    status = response.status_code
    body = _short_body(response)
    body_lower = body.lower()
    if language == "en":
        lines = [f"{provider} call failed, HTTP {status}."]
        if status == 401:
            lines.append("Likely cause: ARK_API_KEY is invalid, mistyped, or not loaded by the current runtime.")
            lines.append(f"Next step: check or regenerate the key in ModelArk API Key management: {MODELARK_API_KEY_URL}")
        elif status == 403:
            lines.append("Likely cause: the current account, region, or key does not have permission for this model or video-generation service.")
            lines.append(f"Next step: confirm the resource package is purchased and Seedance is activated: {SEEDANCE_TUTORIAL_URL}")
            lines.append(f"Also enable Doubao Seed 2.0 Pro permission in model management: {MODEL_OPEN_MANAGEMENT_URL}")
        elif status == 429:
            lines.append("Likely cause: rate limit, too much concurrency, insufficient quota, or unavailable resource-package balance.")
            lines.append(f"Next step: retry later and check the Seedance 2.0 resource package: {SEEDANCE_RESOURCE_PACKAGE_URL}")
        elif status == 400 and any(token in body_lower for token in ("quota", "resource", "package", "payment", "billing", "insufficient", "余额", "资源包", "欠费", "额度")):
            lines.append("Likely cause: Seedance 2.0 resource package is not purchased, not active, out of balance, or the model settings exceed the entitlement.")
            lines.append(f"Next step: check the resource package and video-generation API requirements: {SEEDANCE_RESOURCE_PACKAGE_URL} / {VIDEO_GENERATION_API_URL}")
        elif status >= 500:
            lines.append("Likely cause: provider service is temporarily unavailable or upstream timed out.")
            lines.append("Next step: retry later; if it persists, contact platform support with the status code and request time.")
        else:
            lines.append("Likely cause: request parameters, model permission, or service status are abnormal.")
            lines.append(f"Next step: compare the request with the video-generation API docs: {VIDEO_GENERATION_API_URL}")
        lines.append(f"Response summary: {body}")
        return "\n".join(lines)

    lines = [f"{provider} 调用失败，HTTP {status}。"]

    if status == 401:
        lines.append("可能原因：ARK_API_KEY 无效、填错，或当前运行环境没有读取到正确 key。")
        lines.append(f"处理方式：到 ModelArk API Key 页面检查或重新生成 key：{MODELARK_API_KEY_URL}")
    elif status == 403:
        lines.append("可能原因：当前账号、区域或 key 没有这个模型/视频生成服务的权限。")
        lines.append(f"处理方式：确认已按流程购买资源包并激活 Seedance：{SEEDANCE_TUTORIAL_URL}")
        lines.append(f"同时到模型开通管理页开启 Doubao Seed 2.0 Pro 权限：{MODEL_OPEN_MANAGEMENT_URL}")
    elif status == 429:
        lines.append("可能原因：请求限流、并发过高、额度不足，或资源包余额/配额不可用。")
        lines.append(f"处理方式：稍后重试，并检查 Seedance 2.0 资源包状态：{SEEDANCE_RESOURCE_PACKAGE_URL}")
    elif status == 400 and any(token in body_lower for token in ("quota", "resource", "package", "payment", "billing", "insufficient", "余额", "资源包", "欠费", "额度")):
        lines.append("可能原因：Seedance 2.0 资源包未购买、未生效、余额不足，或模型参数不在当前权益范围内。")
        lines.append(f"处理方式：检查资源包和视频生成 API 要求：{SEEDANCE_RESOURCE_PACKAGE_URL} / {VIDEO_GENERATION_API_URL}")
    elif status >= 500:
        lines.append("可能原因：服务端暂时不可用或上游超时。")
        lines.append("处理方式：稍后重试；如果持续失败，带上状态码和请求时间联系平台支持。")
    else:
        lines.append("可能原因：请求参数、模型权限或服务状态异常。")
        lines.append(f"处理方式：对照视频生成 API 文档检查：{VIDEO_GENERATION_API_URL}")

    lines.append(f"返回摘要：{body}")
    return "\n".join(lines)


def format_seedance_task_failure(*, task_id: str, code: str, message: str, language: str = "zh") -> str:
    if language == "en":
        text = f"Seedance task failed, task_id={task_id}, code={code or 'unknown'}."
        lower = f"{code} {message}".lower()
        hints: list[str] = []
        if "outputaudiosensitivecontentdetected" in lower:
            hints.append("Audio safety check failed; when allowed, the runner retries with stricter abstract instrumental constraints.")
        if any(token in lower for token in ("quota", "resource", "package", "payment", "billing", "insufficient", "余额", "资源包", "欠费", "额度")):
            hints.append(f"Check Seedance 2.0 resource-package balance or service permission: {SEEDANCE_RESOURCE_PACKAGE_URL}")
        if any(token in lower for token in ("permission", "forbidden", "unauthorized", "access")):
            hints.append(f"Check ARK_API_KEY: {MODELARK_API_KEY_URL}")
            hints.append(f"Confirm Doubao Seed 2.0 Pro permission is enabled: {MODEL_OPEN_MANAGEMENT_URL}")
        if not hints:
            hints.append(f"Check the video-generation API docs and task details: {VIDEO_GENERATION_API_URL}")
        hints.append(f"Provider message: {message}")
        return text + "\n" + "\n".join(hints)

    text = f"Seedance 任务失败，task_id={task_id}，code={code or 'unknown'}。"
    lower = f"{code} {message}".lower()
    hints: list[str] = []
    if "outputaudiosensitivecontentdetected" in lower:
        hints.append("音频安全校验未通过；runner 会在允许时用更严格的抽象纯音乐约束自动重试。")
    if any(token in lower for token in ("quota", "resource", "package", "payment", "billing", "insufficient", "余额", "资源包", "欠费", "额度")):
        hints.append(f"请检查 Seedance 2.0 资源包、余额或服务权限：{SEEDANCE_RESOURCE_PACKAGE_URL}")
    if any(token in lower for token in ("permission", "forbidden", "unauthorized", "access")):
        hints.append(f"请检查 ARK_API_KEY：{MODELARK_API_KEY_URL}")
        hints.append(f"请确认 Doubao Seed 2.0 Pro 模型权限已开启：{MODEL_OPEN_MANAGEMENT_URL}")
    if not hints:
        hints.append(f"请对照视频生成 API 文档和任务详情排查：{VIDEO_GENERATION_API_URL}")
    hints.append(f"返回信息：{message}")
    return text + "\n" + "\n".join(hints)
