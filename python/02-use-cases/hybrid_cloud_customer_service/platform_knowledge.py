"""Hybrid-cloud Cloud Search knowledge adapter using AgentKit's REST contract."""

from __future__ import annotations

import os
import logging
from urllib.parse import urlparse

import requests


logger = logging.getLogger(__name__)


def normalize_knowledge_tool_metadata(tools: list[object]) -> None:
    """Keep VeADK's load_knowledgebase metadata JSON-safe.

    VeADK 0.5.40 stores the backend object itself in
    ``LoadKnowledgebaseTool.custom_metadata["backend"]``.  AgentKit/ADK
    telemetry expects custom metadata values to be JSON-safe and may place
    them in a set while processing a tool call.  Pydantic backend instances
    are mutable and unhashable, so replace only that diagnostic value with
    its stable class name.  The tool continues to use its original
    ``knowledgebase`` object for searches.
    """
    for tool in tools:
        if getattr(tool, "name", "") != "load_knowledgebase":
            continue
        metadata = getattr(tool, "custom_metadata", None)
        if not isinstance(metadata, dict):
            continue
        backend = metadata.get("backend")
        if backend is not None and not isinstance(
            backend, (str, int, float, bool)
        ):
            metadata["backend"] = type(backend).__name__


def _bearer_token() -> str:
    """Return only the platform-injected Knowledge service credential."""
    return os.getenv("KNOWLEDGE_BEARER_TOKEN", "").strip()


def _knowledge_endpoint() -> str:
    """Return the published Knowledge HTTP base URL."""
    endpoint = os.getenv("KNOWLEDGE_BASE_URL", "").strip().rstrip("/")
    parsed = urlparse(endpoint)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return endpoint
    if endpoint:
        # The AgentKit console displays the Knowledge service name/ID (kb-*) in
        # its curl example without a scheme in some versions. Do not guess an
        # endpoint here: a published Runtime injects the actual BaseUrl.
        logger.warning("Knowledge adapter disabled: invalid KNOWLEDGE_BASE_URL")
    return ""


def build_platform_knowledge(app_name: str):
    """Return a VeADK KnowledgeBase or None when no platform binding exists."""
    # Publishing the associated Knowledge resource injects its concrete HTTP
    # endpoint and a short-lived bearer token into the Runtime environment.
    endpoint = _knowledge_endpoint()
    if not endpoint:
        return None

    from veadk.knowledgebase import KnowledgeBase
    from veadk.knowledgebase.backends.base_backend import BaseKnowledgebaseBackend
    from veadk.knowledgebase.entry import KnowledgebaseEntry

    class AgentKitKnowledgeBackend(BaseKnowledgebaseBackend):
        """Read-only backend backed by the published AgentKit Knowledge API."""

        def precheck_index_naming(self) -> None:
            # The platform owns the index; this adapter has no local index to
            # create or validate.
            return None

        def add_from_directory(self, directory: str, *args, **kwargs) -> bool:
            del directory, args, kwargs
            raise RuntimeError("AgentKit Knowledge is managed through the platform console")

        def add_from_files(self, files: list[str], *args, **kwargs) -> bool:
            del files, args, kwargs
            raise RuntimeError("AgentKit Knowledge is managed through the platform console")

        def add_from_text(self, text: str | list[str], *args, **kwargs) -> bool:
            del text, args, kwargs
            raise RuntimeError("AgentKit Knowledge is managed through the platform console")

        def search(self, query: str, top_k: int = 3, **kwargs):
            del kwargs
            token = _bearer_token()
            if not token:
                # An inbound Runtime JWT/API key is scoped to the Runtime gateway
                # and must never be forwarded to a downstream Knowledge service.
                logger.warning("Knowledge search skipped: no published Knowledge credential")
                return []
            response = requests.post(
                f"{endpoint}/v1/search",
                json={"question": query, "history_chats": [], "top_k": top_k},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=20,
            )
            response.raise_for_status()
            documents = response.json().get("documents", [])
            logger.info("Knowledge search completed: query=%r hits=%d", query, len(documents))
            entries = []
            for document in documents:
                content = document.get("content", {})
                if isinstance(content, dict):
                    content = content.get("content", "")
                entries.append(
                    KnowledgebaseEntry(content=str(content), metadata=document.get("metadata", {}))
                )
            return entries

    # Supplying a backend instance is essential: otherwise KnowledgeBase
    # defaults to its local llama-index backend during model_post_init, which
    # is neither needed nor installed in the Runtime image.
    return KnowledgeBase(
        app_name=app_name,
        backend=AgentKitKnowledgeBackend(index=app_name),
        name="agentkit_published_knowledge",
        description="Published AgentKit Knowledge resource",
    )
