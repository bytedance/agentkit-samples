import os
from typing import Optional, Tuple

from rich.console import Console
from volcenginesdkarkruntime import Ark

console = Console()

# Ark configuration read from environment
MODEL_AGENT_API_KEY = os.getenv("MODEL_AGENT_API_KEY")
ARK_BASE_URL = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
ARK_TEXT_EMBEDDING_MODEL = os.getenv(
    "ARK_TEXT_EMBEDDING_MODEL", "doubao-embedding-text-240715"
)
ARK_MULTIMODAL_EMBEDDING_MODEL = os.getenv(
    "ARK_MODEL_ID", "doubao-embedding-vision-250615"
)

# Cached clients
_ark_client: Optional[Ark] = None


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
