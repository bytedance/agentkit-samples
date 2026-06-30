from __future__ import annotations

import importlib.util
import socket
import sys
import types
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "market-agent"
    / "src"
    / "market_agent"
    / "tools"
    / "web_parser_local.py"
)

class FakeLogger:
    def info(self, *args, **kwargs):
        return None

    def debug(self, *args, **kwargs):
        return None

    def error(self, *args, **kwargs):
        return None


def load_module(monkeypatch):
    playwright_module = types.ModuleType("playwright.async_api")
    playwright_module.async_playwright = lambda: None
    logger_module = types.ModuleType("veadk.utils.logger")
    logger_module.get_logger = lambda name: FakeLogger()
    monkeypatch.setitem(sys.modules, "playwright.async_api", playwright_module)
    monkeypatch.setitem(sys.modules, "veadk.utils.logger", logger_module)

    spec = importlib.util.spec_from_file_location("web_parser_local_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_is_public_ip_accepts_public_resolved_address(monkeypatch):
    module = load_module(monkeypatch)
    monkeypatch.setattr(socket, "gethostbyname", lambda host: "resolved-address")
    monkeypatch.setattr(
        module.ipaddress,
        "ip_address",
        lambda value: types.SimpleNamespace(is_global=True),
    )

    assert module._is_public_ip("https://example.com/page") is True


def test_is_public_ip_rejects_non_global_resolved_address(monkeypatch):
    module = load_module(monkeypatch)
    monkeypatch.setattr(socket, "gethostbyname", lambda host: "resolved-address")
    monkeypatch.setattr(
        module.ipaddress,
        "ip_address",
        lambda value: types.SimpleNamespace(is_global=False),
    )

    assert module._is_public_ip("http://localhost:8000") is False


def test_is_public_ip_rejects_malformed_url(monkeypatch):
    module = load_module(monkeypatch)

    assert module._is_public_ip("not-a-url") is False


def test_is_public_ip_rejects_dns_errors(monkeypatch):
    module = load_module(monkeypatch)

    def raise_dns_error(host):
        raise OSError("dns failed")

    monkeypatch.setattr(socket, "gethostbyname", raise_dns_error)

    assert module._is_public_ip("https://example.com") is False
