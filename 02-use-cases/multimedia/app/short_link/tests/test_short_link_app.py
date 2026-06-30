from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

import pytest
from fastapi import HTTPException


MODULE_PATH = Path(__file__).resolve().parents[1] / "app.py"


def load_module(monkeypatch):
    monkeypatch.setenv("SHORT_LINK_MODE", "dict")
    monkeypatch.setenv("SHORT_LINK_DOMAIN", "https://short.example")
    spec = importlib.util.spec_from_file_location("short_link_app_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.dict_storage["auto_id_counter"] = 0
    module.dict_storage["long_md5"].clear()
    module.dict_storage["short"].clear()
    return module


@pytest.mark.parametrize(
    ("unique_id", "short_code"),
    [
        (0, "0"),
        (1, "1"),
        (61, "z"),
        (62, "10"),
        (3843, "zz"),
        (3844, "100"),
    ],
)
def test_encode_id_converts_integer_to_base62(monkeypatch, unique_id, short_code):
    module = load_module(monkeypatch)

    assert module.encode_id(unique_id) == short_code


def test_shorten_url_creates_and_reuses_short_code(monkeypatch):
    module = load_module(monkeypatch)
    request = module.URLRequest(url="https://example.com/article")

    first = asyncio.run(module.shorten_url(request))
    second = asyncio.run(module.shorten_url(request))

    assert first == second
    assert first["short_code"] == "1"
    assert first["short_url"] == "https://short.example/t/1"


def test_shorten_url_includes_resource_type_in_short_url(monkeypatch):
    module = load_module(monkeypatch)

    response = asyncio.run(
        module.shorten_url(
            module.URLRequest(url="https://example.com/image.png", type="image")
        )
    )

    assert response["short_url"] == "https://short.example/t/image/1"


def test_redirect_url_returns_original_url(monkeypatch):
    module = load_module(monkeypatch)
    created = asyncio.run(
        module.shorten_url(
            module.URLRequest(url='"https://example.com/video.mp4"', type="video")
        )
    )

    assert (
        asyncio.run(module.redirect_url(created["short_code"], type="video"))
        == "https://example.com/video.mp4"
    )


def test_redirect_url_raises_404_for_unknown_code(monkeypatch):
    module = load_module(monkeypatch)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(module.redirect_url("missing"))

    assert exc_info.value.status_code == 404
