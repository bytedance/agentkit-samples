"""
豆包官方 API 调用封装
支持文本模型（/chat/completions）和视觉模型（/responses）

文本模型：标准 OpenAI 兼容格式
视觉模型：豆包专有 Responses API 格式
  - endpoint: /api/v3/responses
  - 请求体：只有 model + input（无 temperature/parameters 等）
  - input content 类型：input_text / input_image（非 text / image_url）
  - 参考：https://www.volcengine.com/docs/82379/1541595
"""

import json
import logging
import os
from typing import List, Dict, Any, Optional

import httpx

logger = logging.getLogger(__name__)


class DoubaoClient:
    """豆包 API 客户端"""

    def __init__(
        self,
        api_key: str,
        api_base: str = "https://ark.cn-beijing.volces.com/api/v3",
        timeout: int = 120,
    ):
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    # ==================== 文本模型 ====================

    async def text_completion(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        调用豆包文本模型 API（标准 /chat/completions endpoint）

        Args:
            model: 模型名称，如 "doubao-seed-1-6-251015"
            messages: 标准 OpenAI 格式消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数

        Returns:
            标准 OpenAI 兼容格式响应
        """
        url = f"{self.api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        payload.update(kwargs)

        logger.debug(f"豆包文本 API 请求: model={model}, messages={len(messages)} 条")

        try:
            response = await self.client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            logger.debug("豆包文本 API 响应成功")
            return result
        except httpx.HTTPStatusError as e:
            logger.error(
                f"豆包文本 API HTTP 错误: {e.response.status_code} - {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"豆包文本 API 调用失败: {e}")
            raise

    # ==================== 视觉模型 ====================

    async def vision_completion(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        **kwargs,
    ) -> Dict[str, Any]:
        """
        调用豆包视觉模型 API（/responses endpoint，豆包专有格式）

        请求格式严格按照官方文档：
        {
            "model": "doubao-seed-1-6-vision-250815",
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_image", "image_url": "https://..."},
                        {"type": "input_text", "text": "你看见了什么？"}
                    ]
                }
            ]
        }

        Args:
            model: 视觉模型名称，如 "doubao-seed-1-6-vision-250815"
            messages: 标准 OpenAI 格式消息列表（会自动转换为豆包格式）

        Returns:
            转换为标准 OpenAI 格式的响应（方便上层代码统一处理）
        """
        url = f"{self.api_base}/responses"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # 将标准 OpenAI messages 转换为豆包 Responses API 格式
        doubao_input = self._convert_messages_to_doubao_input(messages)

        # ⚠️ 严格按照官方文档：只有 model + input，不传任何其他字段
        payload = {
            "model": model,
            "input": doubao_input,
        }

        logger.debug(f"豆包视觉 API 请求: model={model}, input={len(doubao_input)} 条")

        try:
            response = await self.client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            raw = response.json()

            # 转换为统一的 OpenAI 格式
            return self._convert_vision_response(raw)
        except httpx.HTTPStatusError as e:
            logger.error(
                f"豆包视觉 API HTTP 错误: {e.response.status_code} - {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"豆包视觉 API 调用失败: {e}")
            raise

    # ==================== 格式转换 ====================

    @staticmethod
    def _convert_messages_to_doubao_input(
        messages: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        将标准 OpenAI messages 转换为豆包 Responses API 的 input 格式

        OpenAI 格式 → 豆包格式:
          "text"      → "input_text"
          "image_url" → "input_image"  (且 image_url 从嵌套对象变为字符串)
          "system"    → 作为 input_text 加入（豆包 vision 不区分 system）
        """
        doubao_input: List[Dict[str, Any]] = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            # system message → 转为 user 的 input_text（豆包 vision API 可能不支持 system role）
            if role == "system":
                if isinstance(content, str):
                    doubao_input.append(
                        {
                            "role": "user",
                            "content": [
                                {"type": "input_text", "text": f"[系统提示] {content}"}
                            ],
                        }
                    )
                continue

            # content 是纯字符串
            if isinstance(content, str):
                doubao_input.append(
                    {
                        "role": role,
                        "content": [{"type": "input_text", "text": content}],
                    }
                )
                continue

            # content 是列表（多模态内容）
            doubao_content: List[Dict[str, Any]] = []
            for item in content:
                item_type = item.get("type", "")

                if item_type == "text":
                    doubao_content.append(
                        {
                            "type": "input_text",
                            "text": item["text"],
                        }
                    )
                elif item_type == "image_url":
                    # 提取 URL（OpenAI 格式可能是 {"url": "..."} 或字符串）
                    url_data = item.get("image_url")
                    url = (
                        url_data.get("url") if isinstance(url_data, dict) else url_data
                    )
                    doubao_content.append(
                        {
                            "type": "input_image",
                            "image_url": url,
                        }
                    )
                else:
                    # 未知类型保持原样
                    doubao_content.append(item)

            doubao_input.append(
                {
                    "role": role,
                    "content": doubao_content,
                }
            )

        return doubao_input

    @staticmethod
    def _convert_vision_response(raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        将豆包 Responses API 响应转换为 OpenAI Chat Completions 格式

        豆包 Responses API 实际响应格式：
        {
            "id": "resp_...",
            "model": "doubao-seed-1-6-vision-250815",
            "output": [
                {"type": "reasoning", "summary": [{"type": "summary_text", "text": "..."}]},
                {"type": "message", "content": [{"type": "output_text", "text": "最终回答"}]}
            ],
            "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}
        }
        """
        # 如果已经是 OpenAI 格式（有 choices 字段），直接返回
        if "choices" in raw:
            return raw

        content_text = ""

        # output 是一个列表，从中提取 type="message" 的项
        output_list = raw.get("output", [])
        if isinstance(output_list, list):
            for item in output_list:
                if not isinstance(item, dict):
                    continue
                item_type = item.get("type", "")

                # 主回答内容：type="message"
                if item_type == "message":
                    content_parts = item.get("content", [])
                    for part in content_parts:
                        if isinstance(part, dict) and part.get("type") == "output_text":
                            content_text += part.get("text", "")
                        elif isinstance(part, str):
                            content_text += part

        # 如果没有从 message 中提取到内容，尝试其他方式
        if not content_text:
            # 尝试从 output 中任何 summary_text 提取
            if isinstance(output_list, list):
                for item in output_list:
                    if isinstance(item, dict):
                        for s in item.get("summary", []):
                            if isinstance(s, dict) and s.get("type") == "summary_text":
                                content_text += s.get("text", "")

        # 最终兜底
        if not content_text:
            content_text = json.dumps(raw, ensure_ascii=False)
            logger.warning(
                f"豆包视觉 API 响应中未找到 message 内容，完整响应: {content_text[:300]}"
            )

        # 提取 usage
        usage = raw.get("usage", {})
        input_tokens = usage.get("input_tokens", usage.get("prompt_tokens", 0))
        output_tokens = usage.get("output_tokens", usage.get("completion_tokens", 0))

        return {
            "id": raw.get("id", ""),
            "object": "chat.completion",
            "created": raw.get("created_at", 0),
            "model": raw.get("model", ""),
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content_text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
        }

    async def close(self):
        """关闭客户端"""
        await self.client.aclose()


# ==================== 便捷函数 ====================


async def call_doubao_text(
    model: str,
    messages: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    """便捷函数：调用豆包文本模型"""
    if not api_key:
        api_key = os.getenv("MODEL_AGENT_API_KEY")
        if not api_key:
            raise ValueError("API Key 未提供，且环境变量 MODEL_AGENT_API_KEY 未设置")
    if not api_base:
        api_base = os.getenv(
            "MODEL_AGENT_API_BASE", "https://ark.cn-beijing.volces.com/api/v3"
        )

    async with DoubaoClient(api_key=api_key, api_base=api_base) as client:
        return await client.text_completion(model=model, messages=messages, **kwargs)


async def call_doubao_vision(
    model: str,
    messages: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    """便捷函数：调用豆包视觉模型（自动转换为 Responses API 格式）"""
    if not api_key:
        api_key = os.getenv("MODEL_VISION_API_KEY")
        if not api_key:
            raise ValueError("API Key 未提供，且环境变量 MODEL_VISION_API_KEY 未设置")
    if not api_base:
        api_base = os.getenv(
            "MODEL_VISION_API_BASE", "https://ark.cn-beijing.volces.com/api/v3"
        )

    async with DoubaoClient(api_key=api_key, api_base=api_base) as client:
        return await client.vision_completion(model=model, messages=messages, **kwargs)
