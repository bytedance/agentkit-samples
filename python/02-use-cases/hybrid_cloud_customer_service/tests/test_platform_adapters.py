from __future__ import annotations

import json
import sys
from types import ModuleType, SimpleNamespace

import pytest
import requests

import platform_knowledge
import platform_memory
from platform_request_context import _request_authorization


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self.payload


def install_fake_veadk(monkeypatch) -> None:
    veadk = ModuleType("veadk")
    memory = ModuleType("veadk.memory")
    ltm_backends = ModuleType("veadk.memory.long_term_memory_backends")
    base_backend = ModuleType("veadk.memory.long_term_memory_backends.base_backend")
    knowledgebase = ModuleType("veadk.knowledgebase")
    kb_backends = ModuleType("veadk.knowledgebase.backends")
    kb_base_backend = ModuleType("veadk.knowledgebase.backends.base_backend")
    entry = ModuleType("veadk.knowledgebase.entry")

    class BaseLongTermMemoryBackend:
        def __init__(self, index: str) -> None:
            self.index = index

    class LongTermMemory:
        def __init__(self, **kwargs) -> None:
            self.__dict__.update(kwargs)

    class BaseKnowledgebaseBackend:
        def __init__(self, index: str) -> None:
            self.index = index

    class KnowledgeBase:
        def __init__(self, app_name: str, backend=None, **kwargs) -> None:
            self.app_name = app_name
            self.backend = backend
            self.__dict__.update(kwargs)

        def search(self, query: str, top_k: int = 3, **kwargs):
            return self.backend.search(query, top_k=top_k, **kwargs)

    class KnowledgebaseEntry:
        def __init__(self, content: str, metadata: dict) -> None:
            self.content = content
            self.metadata = metadata

    memory.LongTermMemory = LongTermMemory
    base_backend.BaseLongTermMemoryBackend = BaseLongTermMemoryBackend
    knowledgebase.KnowledgeBase = KnowledgeBase
    kb_base_backend.BaseKnowledgebaseBackend = BaseKnowledgebaseBackend
    entry.KnowledgebaseEntry = KnowledgebaseEntry
    for name, module in {
        "veadk": veadk,
        "veadk.memory": memory,
        "veadk.memory.long_term_memory_backends": ltm_backends,
        "veadk.memory.long_term_memory_backends.base_backend": base_backend,
        "veadk.knowledgebase": knowledgebase,
        "veadk.knowledgebase.backends": kb_backends,
        "veadk.knowledgebase.backends.base_backend": kb_base_backend,
        "veadk.knowledgebase.entry": entry,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)


@pytest.mark.parametrize("wrapped", [False, True], ids=["array", "documents-envelope"])
@pytest.mark.parametrize("nested_content", [False, True], ids=["text", "nested-text"])
def test_platform_knowledge_search(monkeypatch, wrapped, nested_content) -> None:
    install_fake_veadk(monkeypatch)
    monkeypatch.setenv("KNOWLEDGE_BASE_URL", "https://knowledge.example")
    monkeypatch.setenv("KNOWLEDGE_BEARER_TOKEN", "knowledge-service-token")
    token = _request_authorization.set("Bearer inbound-runtime-token")
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        content = {"content": "退款期为七天"} if nested_content else "退款期为七天"
        documents = [{"content": content, "metadata": {"id": 1}}]
        return FakeResponse({"documents": documents} if wrapped else documents)

    monkeypatch.setattr(platform_knowledge.requests, "post", fake_post)
    try:
        knowledge = platform_knowledge.build_platform_knowledge("demo")
        results = knowledge.search("退款规则", top_k=2)
    finally:
        _request_authorization.reset(token)

    assert results[0].content == "退款期为七天"
    assert results[0].metadata == {"id": 1}
    assert len(results) == 1
    assert calls[0][0] == "https://knowledge.example/v1/search"
    assert calls[0][1]["headers"]["Authorization"] == "Bearer knowledge-service-token"
    assert calls[0][1]["json"]["top_k"] == 2


def test_platform_knowledge_search_cloud_search_result_array(monkeypatch) -> None:
    """Preserve the field layout observed on E97, using synthetic document data."""
    install_fake_veadk(monkeypatch)
    monkeypatch.setenv("KNOWLEDGE_BASE_URL", "https://knowledge.example")
    monkeypatch.setenv("KNOWLEDGE_BEARER_TOKEN", "knowledge-service-token")
    documents = [
        {
            "id": f"document-{index}",
            "metadata": {
                "retrieval_score": 0.8,
                "retrieval_index": index,
                "rerank_index": index,
                "rerank_score": 0.9,
            },
            "score": 0.9,
            "content": {"title": "退款政策", "content": content},
        }
        for index, content in enumerate(["退款期为七天", "退款需要本人确认"])
    ]
    monkeypatch.setattr(
        platform_knowledge.requests, "post", lambda *args, **kwargs: FakeResponse(documents)
    )

    results = platform_knowledge.build_platform_knowledge("demo").search("退款规则")

    assert [entry.content for entry in results] == ["退款期为七天", "退款需要本人确认"]
    assert [entry.metadata for entry in results] == [document["metadata"] for document in documents]


@pytest.mark.parametrize("payload", [[], {"documents": []}], ids=["array", "envelope"])
def test_platform_knowledge_empty_search(monkeypatch, payload) -> None:
    install_fake_veadk(monkeypatch)
    monkeypatch.setenv("KNOWLEDGE_BASE_URL", "https://knowledge.example")
    monkeypatch.setenv("KNOWLEDGE_BEARER_TOKEN", "knowledge-service-token")
    monkeypatch.setattr(
        platform_knowledge.requests, "post", lambda *args, **kwargs: FakeResponse(payload)
    )

    assert platform_knowledge.build_platform_knowledge("demo").search("退款规则") == []


@pytest.mark.parametrize(
    "payload",
    [
        None,
        "invalid",
        1,
        {},
        {"error": "invalid query"},
        {"documents": None},
        {"documents": {}},
        {"documents": "invalid"},
        [None],
        ["invalid"],
        {"documents": [None]},
    ],
)
def test_platform_knowledge_rejects_malformed_response(monkeypatch, payload) -> None:
    install_fake_veadk(monkeypatch)
    monkeypatch.setenv("KNOWLEDGE_BASE_URL", "https://knowledge.example")
    monkeypatch.setenv("KNOWLEDGE_BEARER_TOKEN", "knowledge-service-token")
    monkeypatch.setattr(
        platform_knowledge.requests, "post", lambda *args, **kwargs: FakeResponse(payload)
    )

    with pytest.raises(ValueError, match="Knowledge search"):
        platform_knowledge.build_platform_knowledge("demo").search("退款规则")


def test_platform_knowledge_preserves_http_error(monkeypatch) -> None:
    install_fake_veadk(monkeypatch)
    monkeypatch.setenv("KNOWLEDGE_BASE_URL", "https://knowledge.example")
    monkeypatch.setenv("KNOWLEDGE_BEARER_TOKEN", "knowledge-service-token")

    def fail_http():
        raise requests.HTTPError("403 Forbidden")

    def unexpected_json():
        raise AssertionError("HTTP errors must be raised before parsing the response")

    monkeypatch.setattr(
        platform_knowledge.requests,
        "post",
        lambda *args, **kwargs: SimpleNamespace(raise_for_status=fail_http, json=unexpected_json),
    )

    with pytest.raises(requests.HTTPError, match="403 Forbidden"):
        platform_knowledge.build_platform_knowledge("demo").search("退款规则")


def test_platform_knowledge_does_not_forward_inbound_runtime_token(monkeypatch) -> None:
    install_fake_veadk(monkeypatch)
    monkeypatch.setenv("KNOWLEDGE_BASE_URL", "https://knowledge.example")
    monkeypatch.delenv("KNOWLEDGE_BEARER_TOKEN", raising=False)
    token = _request_authorization.set("Bearer inbound-runtime-token")

    def unexpected_post(*args, **kwargs):
        del args, kwargs
        raise AssertionError("inbound Runtime token must not reach Knowledge")

    monkeypatch.setattr(platform_knowledge.requests, "post", unexpected_post)
    try:
        knowledge = platform_knowledge.build_platform_knowledge("demo")
        assert knowledge.search("退款规则") == []
    finally:
        _request_authorization.reset(token)


def test_platform_knowledge_rejects_raw_knowledge_service_id(monkeypatch) -> None:
    install_fake_veadk(monkeypatch)
    monkeypatch.setenv("KNOWLEDGE_BASE_URL", "kb-test-knowledge")
    assert platform_knowledge.build_platform_knowledge("demo") is None


def test_knowledge_tool_metadata_is_json_safe(monkeypatch) -> None:
    install_fake_veadk(monkeypatch)
    monkeypatch.setenv("KNOWLEDGE_BASE_URL", "https://knowledge.example")
    knowledge = platform_knowledge.build_platform_knowledge("demo")
    tool = SimpleNamespace(
        name="load_knowledgebase",
        custom_metadata={"backend": knowledge.backend},
    )

    platform_knowledge.normalize_knowledge_tool_metadata([tool])

    assert tool.custom_metadata == {"backend": "AgentKitKnowledgeBackend"}
    assert json.loads(json.dumps(tool.custom_metadata)) == tool.custom_metadata


def test_platform_memory_save_and_search(monkeypatch) -> None:
    install_fake_veadk(monkeypatch)
    monkeypatch.setenv("DATABASE_MEM0_BASE_URL", "https://memory.example")
    monkeypatch.setenv("DATABASE_MEM0_API_KEY", "test-key")
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/search/"):
            return FakeResponse({"results": [{"memory": "偏好快速到账"}]})
        return FakeResponse({"status": "accepted"})

    monkeypatch.setattr(platform_memory.requests, "post", fake_post)
    memory = platform_memory.build_platform_memory("demo")
    backend = memory.backend

    assert backend.precheck_index_naming() is True
    assert backend.save_memory("user-1", ["用户偏好快速到账", "上次退款已确认"]) is True
    assert backend.search_memory("user-1", "到账偏好", 3) == ["偏好快速到账"]
    assert calls[0][0] == "https://memory.example/v1/memories/"
    assert calls[1][0] == "https://memory.example/v1/memories/search/"
    assert calls[0][1]["headers"]["Authorization"] == "Token test-key"
    assert len(calls[0][1]["json"]["messages"]) == 2
    assert calls[1][1]["json"] == {
        "query": "到账偏好",
        "user_id": "user-1",
        "output_format": "v1.1",
        "top_k": 3,
    }


def test_memory_tool_metadata_is_json_safe(monkeypatch) -> None:
    install_fake_veadk(monkeypatch)
    monkeypatch.setenv("DATABASE_MEM0_BASE_URL", "https://memory.example")
    monkeypatch.setenv("DATABASE_MEM0_API_KEY", "test-key")
    memory = platform_memory.build_platform_memory("demo")
    tool = SimpleNamespace(
        name="load_memory",
        custom_metadata={"backend": memory.backend},
    )

    platform_memory.normalize_memory_tool_metadata([tool])

    assert tool.custom_metadata == {"backend": "AgentKitMem0Backend"}
    assert json.loads(json.dumps(tool.custom_metadata)) == tool.custom_metadata
