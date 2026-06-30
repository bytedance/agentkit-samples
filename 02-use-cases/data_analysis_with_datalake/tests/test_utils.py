from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "utils.py"


class FakeConsole:
    def print(self, *args, **kwargs):
        return None


class FakeEmbeddingResponse:
    data = [types.SimpleNamespace(embedding=[0.1, 0.2, 0.3])]


class FakeArk:
    instances = []

    def __init__(self, api_key, base_url):
        self.api_key = api_key
        self.base_url = base_url
        self.embeddings = types.SimpleNamespace(create=self.create_text_embedding)
        self.multimodal_embeddings = types.SimpleNamespace(
            create=self.create_multimodal_embedding
        )
        self.__class__.instances.append(self)

    def create_text_embedding(self, model, input):
        self.last_text_call = {"model": model, "input": input}
        return FakeEmbeddingResponse()

    def create_multimodal_embedding(self, model, input):
        self.last_multimodal_call = {"model": model, "input": input}
        return FakeEmbeddingResponse()


def load_module(monkeypatch, api_key=None):
    FakeArk.instances = []
    if api_key is None:
        monkeypatch.delenv("MODEL_AGENT_API_KEY", raising=False)
    else:
        monkeypatch.setenv("MODEL_AGENT_API_KEY", api_key)
    rich = types.ModuleType("rich")
    rich_console = types.ModuleType("rich.console")
    rich_console.Console = FakeConsole
    ark_module = types.ModuleType("volcenginesdkarkruntime")
    ark_module.Ark = FakeArk
    monkeypatch.setitem(sys.modules, "rich", rich)
    monkeypatch.setitem(sys.modules, "rich.console", rich_console)
    monkeypatch.setitem(sys.modules, "volcenginesdkarkruntime", ark_module)

    spec = importlib.util.spec_from_file_location("datalake_utils_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_get_ark_client_reports_missing_api_key(monkeypatch):
    module = load_module(monkeypatch)

    client, error = module.get_ark_client()

    assert client is None
    assert error == "MODEL_AGENT_API_KEY not set"


def test_get_ark_client_caches_initialized_client(monkeypatch):
    module = load_module(monkeypatch, api_key="test-key")

    first, first_error = module.get_ark_client()
    second, second_error = module.get_ark_client()

    assert first_error is None
    assert second_error is None
    assert first is second
    assert len(FakeArk.instances) == 1
    assert first.api_key == "test-key"


def test_get_text_embedding_wraps_ark_response(monkeypatch):
    module = load_module(monkeypatch, api_key="test-key")

    vector, error = module.get_text_embedding("hello")

    assert error is None
    assert vector == [0.1, 0.2, 0.3]
    assert FakeArk.instances[0].last_text_call["input"] == ["hello"]


def test_get_multimodal_text_vector_uses_text_input(monkeypatch):
    module = load_module(monkeypatch, api_key="test-key")

    vector, error = module.get_multimodal_text_vector("poster")

    assert error is None
    assert vector == [0.1, 0.2, 0.3]
    assert FakeArk.instances[0].last_multimodal_call["input"] == [
        {"type": "text", "text": "poster"}
    ]
