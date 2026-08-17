import json
import os
from datetime import date, datetime, time
from typing import Optional, Tuple

import pandas as pd
from rich.console import Console
from volcenginesdkarkruntime import Ark

console = Console()

provider = os.getenv("CLOUD_PROVIDER", "").strip().lower()
is_byteplus = provider == "byteplus" or (
    not provider and bool(os.getenv("BYTEPLUS_REGION"))
)
default_ark_base_url = (
    "https://ark.ap-southeast.bytepluses.com/api/v3"
    if is_byteplus
    else "https://ark.cn-beijing.volces.com/api/v3"
)

# Ark configuration read from environment
MODEL_AGENT_API_KEY = os.getenv("MODEL_AGENT_API_KEY")
ARK_BASE_URL = os.getenv("ARK_BASE_URL", default_ark_base_url)
ARK_TEXT_EMBEDDING_MODEL = os.getenv(
    "ARK_TEXT_EMBEDDING_MODEL",
    (
        "skylark-embedding-vision-251215"
        if is_byteplus
        else "doubao-embedding-large-text-250515"
    ),
)
ARK_MULTIMODAL_EMBEDDING_MODEL = os.getenv(
    "ARK_MULTIMODAL_EMBEDDING_MODEL",
    os.getenv(
        "ARK_MODEL_ID",
        (
            "skylark-embedding-vision-251215"
            if is_byteplus
            else "doubao-embedding-vision-251215"
        ),
    ),
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
    """获取与当前云厂商匹配的文本向量。

    Function Purpose:
        避免 BytePlus 环境调用国内方舟文本向量模型。

    Implementation Logic:
        国内继续使用标准文本 Embedding API；BytePlus 使用支持纯文本输入的
        Skylark 多模态向量 API，并统一提取响应中的 dense embedding。
    """
    client, error_msg = get_ark_client()
    if error_msg:
        return None, error_msg
    try:
        if is_byteplus:
            resp = client.multimodal_embeddings.create(
                model=ARK_TEXT_EMBEDDING_MODEL,
                input=[{"type": "text", "text": text}],
            )
            return _extract_multimodal_embedding(resp), None
        resp = client.embeddings.create(model=ARK_TEXT_EMBEDDING_MODEL, input=[text])
        return resp.data[0].embedding, None
    except Exception as e:
        error_msg = f"Failed to get text embedding: {e}"
        console.print(f"[red]{error_msg}[/red]")
        return None, error_msg


def get_multimodal_text_vector(text: str) -> Tuple[Optional[list], Optional[str]]:
    """获取多模态检索使用的文本向量。"""
    client, error_msg = get_ark_client()
    if error_msg:
        return None, "MODEL_AGENT_API_KEY 未设置"
    try:
        resp = client.multimodal_embeddings.create(
            model=ARK_MULTIMODAL_EMBEDDING_MODEL,
            input=[{"type": "text", "text": text}],
        )
        return _extract_multimodal_embedding(resp), None
    except Exception as e:
        return None, f"Ark 向量化失败: {e}"


def _extract_multimodal_embedding(response) -> list:
    """从不同 SDK 版本的多模态响应中提取稠密向量。

    Function Purpose:
        兼容 data 为对象或列表的 Ark/ModelArk SDK 响应结构。

    Implementation Logic:
        校验 data 与 embedding 字段，列表结构读取首项，对象结构直接读取；
        响应不完整时抛出明确错误并由调用方转换为工具错误。
    """
    data = getattr(response, "data", None)
    if data is None:
        raise ValueError("Ark 返回为空")
    item = data[0] if isinstance(data, (list, tuple)) else data
    embedding = getattr(item, "embedding", None)
    if embedding is None:
        raise ValueError("Ark 返回中缺少 embedding")
    return embedding
