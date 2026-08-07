import json
import os
from datetime import date, datetime, time
from typing import Optional, Tuple

import pandas as pd
from rich.console import Console
from volcenginesdkarkruntime import Ark

console = Console()

# Ark configuration read from environment
MODEL_AGENT_API_KEY = os.getenv("MODEL_AGENT_API_KEY")
ARK_BASE_URL = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
ARK_TEXT_EMBEDDING_MODEL = os.getenv(
    "ARK_TEXT_EMBEDDING_MODEL", "doubao-embedding-large-text-250515"
)
ARK_MULTIMODAL_EMBEDDING_MODEL = os.getenv(
    "ARK_MODEL_ID", "doubao-embedding-vision-251215"
)

# Cached clients
_ark_client: Optional[Ark] = None


def _json_default(value):
    """将数据工具返回的扩展类型转换为 JSON 原生类型。

    Function Purpose:
        处理 NumPy、Pandas 和日期类型，避免工具响应在 json.dumps 阶段失败。

    Implementation Logic:
        数组转换为列表，NumPy 标量转换为 Python 标量，Pandas 空值转换为
        None，日期时间转换为 ISO 8601 字符串；未知类型继续抛出 TypeError。
    """
    if value is pd.NA or value is pd.NaT:
        return None
    if type(value).__module__.split(".", 1)[0] == "numpy":
        if hasattr(value, "tolist"):
            return value.tolist()
        if hasattr(value, "item"):
            return value.item()
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def dumps_json(value) -> str:
    """将工具响应安全地序列化为 JSON 字符串。

    Function Purpose:
        为所有数据查询工具提供一致的 JSON 序列化入口。

    Implementation Logic:
        使用标准 json.dumps 保持原有响应格式，并通过 _json_default 递归处理
        DataFrame 单元格中无法由标准 JSON 编码器直接处理的扩展类型。
    """
    return json.dumps(value, ensure_ascii=False, default=_json_default)


def get_ark_client() -> Tuple[Optional[Ark], Optional[str]]:
    """Initialize and cache Ark client from volcenginesdkarkruntime."""
    global _ark_client
    if _ark_client is not None:
        return _ark_client, None

    if not MODEL_AGENT_API_KEY:
        return None, "MODEL_AGENT_API_KEY not set"
    try:
        _ark_client = Ark(api_key=MODEL_AGENT_API_KEY, base_url=ARK_BASE_URL)
        return _ark_client, None
    except Exception as e:
        return None, f"Failed to init Ark client: {e}"


def get_text_embedding(text: str) -> Tuple[Optional[list], Optional[str]]:
    """Get text embedding using Ark client."""
    client, error_msg = get_ark_client()
    if error_msg:
        return None, error_msg
    try:
        resp = client.embeddings.create(model=ARK_TEXT_EMBEDDING_MODEL, input=[text])
        return resp.data[0].embedding, None
    except Exception as e:
        error_msg = f"Failed to get text embedding: {e}"
        console.print(f"[red]{error_msg}[/red]")
        return None, error_msg


def get_multimodal_text_vector(text: str) -> Tuple[Optional[list], Optional[str]]:
    """Get multimodal text vector using Ark client."""
    client, error_msg = get_ark_client()
    if error_msg:
        return None, "MODEL_AGENT_API_KEY 未设置"
    try:
        resp = client.multimodal_embeddings.create(
            model=ARK_MULTIMODAL_EMBEDDING_MODEL,
            input=[{"type": "text", "text": text}],
        )
        data = getattr(resp, "data", None)
        if data is None:
            return None, "Ark 返回为空"
        vec = data[0].embedding if hasattr(data, "__getitem__") else data.embedding
        return vec, None
    except Exception as e:
        return None, f"Ark 向量化失败: {e}"
