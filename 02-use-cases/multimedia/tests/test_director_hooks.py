from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


DIRECTOR_HOOK_DIR = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "director-agent"
    / "src"
    / "director_agent"
    / "hook"
)


class FakeLogger:
    def debug(self, *args, **kwargs):
        return None

    def warning(self, *args, **kwargs):
        return None

    def error(self, *args, **kwargs):
        return None


def install_hook_stubs(monkeypatch):
    google_tools = types.ModuleType("google.adk.tools")
    google_tools.BaseTool = object
    google_tools.ToolContext = object
    logger_module = types.ModuleType("veadk.utils.logger")
    logger_module.get_logger = lambda name: FakeLogger()
    monkeypatch.setitem(sys.modules, "google.adk.tools", google_tools)
    monkeypatch.setitem(sys.modules, "veadk.utils.logger", logger_module)


def load_hook_module(monkeypatch, filename, module_name):
    install_hook_stubs(monkeypatch)
    spec = importlib.util.spec_from_file_location(
        module_name,
        DIRECTOR_HOOK_DIR / filename,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_error_status_formats_standard_tool_error(monkeypatch):
    module = load_hook_module(monkeypatch, "check_and_raise.py", "check_and_raise_test")

    assert module.error_status("image_generate", "bad count") == {
        "status": {
            "success": False,
            "message": "image_generate Error: bad count",
        }
    }


def test_raise_result_error_accepts_matching_image_counts(monkeypatch):
    module = load_hook_module(monkeypatch, "check_and_raise.py", "check_and_raise_test")
    tool = types.SimpleNamespace(name="image_generate")
    args = {"tasks": [{"task_type": "single"}, {"task_type": "group", "max_images": 2}]}
    response = {"success_list": [{"url": "1"}, {"url": "2"}, {"url": "3"}]}

    assert module.raise_result_error(tool, args, object(), response) is None


def test_raise_result_error_reports_mismatched_image_counts(monkeypatch):
    module = load_hook_module(monkeypatch, "check_and_raise.py", "check_and_raise_test")
    tool = types.SimpleNamespace(name="image_generate")
    args = {"tasks": [{"task_type": "group", "max_images": 3}]}
    response = {"success_list": [{"url": "1"}]}

    result = module.raise_result_error(tool, args, object(), response)

    assert result["status"]["success"] is False
    assert "image_generate Error" in result["status"]["message"]
    assert "预期 (3)" in result["status"]["message"]


def test_raise_result_error_accepts_matching_video_counts(monkeypatch):
    module = load_hook_module(monkeypatch, "check_and_raise.py", "check_and_raise_test")
    tool = types.SimpleNamespace(name="video_generate")
    args = {"params": [{"prompt": "a"}, {"prompt": "b"}]}
    response = {"success_list": [{"url": "1"}, {"url": "2"}]}

    assert module.raise_result_error(tool, args, object(), response) is None


def test_raise_result_error_reports_mismatched_video_counts(monkeypatch):
    module = load_hook_module(monkeypatch, "check_and_raise.py", "check_and_raise_test")
    tool = types.SimpleNamespace(name="video_generate")
    args = {"params": [{"prompt": "a"}, {"prompt": "b"}]}
    response = {"success_list": [{"url": "1"}]}

    result = module.raise_result_error(tool, args, object(), response)

    assert result["status"]["success"] is False
    assert "video_generate Error" in result["status"]["message"]
    assert "预期 (2)" in result["status"]["message"]


def test_raise_result_error_ignores_unknown_tool(monkeypatch):
    module = load_hook_module(monkeypatch, "check_and_raise.py", "check_and_raise_test")
    tool = types.SimpleNamespace(name="other_tool")

    assert module.raise_result_error(tool, {}, object(), {}) is None


class FakeResponse:
    def __init__(self, status_code=200, short_url="https://short/link"):
        self.status_code = status_code
        self.short_url = short_url

    def json(self):
        return {"short_url": self.short_url}


def test_shorten_url_impl_returns_short_url(monkeypatch):
    module = load_hook_module(monkeypatch, "shorten_url.py", "shorten_url_hook_test")
    module.shorten_url_service_url = "https://shortener.example"
    calls = []

    def fake_post(url, json):
        calls.append((url, json))
        return FakeResponse(short_url="https://short/image")

    monkeypatch.setattr(module.requests, "post", fake_post)

    assert module.shorten_url_impl("https://origin/image.png", "image") == "https://short/image"
    assert calls == [
        (
            "https://shortener.example/shorten",
            {"url": "https://origin/image.png", "type": "image"},
        )
    ]


def test_shorten_url_impl_returns_original_url_on_failure(monkeypatch):
    module = load_hook_module(monkeypatch, "shorten_url.py", "shorten_url_hook_test")
    module.shorten_url_service_url = "https://shortener.example"
    monkeypatch.setattr(
        module.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(status_code=500),
    )

    assert module.shorten_url_impl("https://origin/video.mp4", "video") == (
        "https://origin/video.mp4"
    )


def test_hook_shorten_url_skips_when_service_is_unset(monkeypatch):
    module = load_hook_module(monkeypatch, "shorten_url.py", "shorten_url_hook_test")
    module.shorten_url_service_url = None

    assert (
        module.hook_shorten_url(types.SimpleNamespace(name="image_generate"), {}, object(), {})
        is None
    )


def test_hook_shorten_url_rewrites_image_success_list(monkeypatch):
    module = load_hook_module(monkeypatch, "shorten_url.py", "shorten_url_hook_test")
    module.shorten_url_service_url = "https://shortener.example"
    monkeypatch.setattr(
        module,
        "shorten_url_impl",
        lambda url, resource_type="resource": f"{resource_type}:{url}",
    )
    response = {
        "success_list": [
            {"url": "https://origin/a.png", "keep_number": 1},
            "not-a-dict",
        ]
    }

    result = module.hook_shorten_url(
        types.SimpleNamespace(name="image_generate"),
        {},
        object(),
        response,
    )

    assert result["success_list"][0]["url"] == "image:https://origin/a.png"
    assert result["success_list"][0]["keep_number"] == 1


def test_hook_shorten_url_rewrites_video_success_list(monkeypatch):
    module = load_hook_module(monkeypatch, "shorten_url.py", "shorten_url_hook_test")
    module.shorten_url_service_url = "https://shortener.example"
    monkeypatch.setattr(
        module,
        "shorten_url_impl",
        lambda url, resource_type="resource": f"{resource_type}:{url}",
    )
    response = {"success_list": [{"url": "https://origin/a.mp4"}]}

    result = module.hook_shorten_url(
        types.SimpleNamespace(name="video_generate"),
        {},
        object(),
        response,
    )

    assert result["success_list"][0]["url"] == "video:https://origin/a.mp4"


def test_hook_shorten_url_ignores_other_tools(monkeypatch):
    module = load_hook_module(monkeypatch, "shorten_url.py", "shorten_url_hook_test")
    module.shorten_url_service_url = "https://shortener.example"

    assert module.hook_shorten_url(types.SimpleNamespace(name="other"), {}, object(), {}) is None
