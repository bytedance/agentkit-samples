from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest


def install_google_adk_stubs():
    google_module = sys.modules.setdefault("google", types.ModuleType("google"))
    adk_module = sys.modules.setdefault("google.adk", types.ModuleType("google.adk"))
    tools_module = sys.modules.setdefault(
        "google.adk.tools", types.ModuleType("google.adk.tools")
    )
    base_tool_module = sys.modules.setdefault(
        "google.adk.tools.base_tool", types.ModuleType("google.adk.tools.base_tool")
    )
    tool_context_module = sys.modules.setdefault(
        "google.adk.tools.tool_context",
        types.ModuleType("google.adk.tools.tool_context"),
    )
    genai_module = sys.modules.setdefault("google.genai", types.ModuleType("google.genai"))
    genai_types_module = sys.modules.setdefault(
        "google.genai.types", types.ModuleType("google.genai.types")
    )

    class BaseTool:
        pass

    class ToolContext:
        pass

    class Part:
        def __init__(self, text):
            self.text = text

    class Content:
        def __init__(self, parts):
            self.parts = parts

    google_module.adk = adk_module
    google_module.genai = genai_module
    adk_module.tools = tools_module
    tools_module.base_tool = base_tool_module
    tools_module.tool_context = tool_context_module
    base_tool_module.BaseTool = BaseTool
    tool_context_module.ToolContext = ToolContext
    genai_module.types = genai_types_module
    genai_types_module.Content = Content
    genai_types_module.Part = Part


install_google_adk_stubs()
MODULE_PATH = Path(__file__).resolve().parents[1] / "callbacks" / "after_tool_callback.py"
SPEC = importlib.util.spec_from_file_location("callback_after_tool", MODULE_PATH)
after_tool_callback = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(after_tool_callback)


def test_filter_pii_masks_default_chinese_patterns():
    text = "手机号13800138000，身份证11010519491231002X，邮箱alice@example.com"

    filtered = after_tool_callback.filter_pii(text, show_logs=False)

    assert "13800138000" not in filtered
    assert "11010519491231002X" not in filtered
    assert "alice@example.com" not in filtered
    assert "[电话号码已隐藏]" in filtered
    assert "[身份证号已隐藏]" in filtered
    assert "[邮箱已隐藏]" in filtered


def test_filter_pii_supports_custom_patterns():
    text = "订单号 ORDER-12345 已经处理，ORDER-67890 等待复核"

    filtered = after_tool_callback.filter_pii(
        text,
        patterns={"订单号": r"ORDER-\d+"},
        show_logs=False,
    )

    assert filtered == "订单号 [订单号已隐藏] 已经处理，[订单号已隐藏] 等待复核"


def test_filter_pii_returns_original_text_when_no_pattern_matches():
    text = "这段内容没有手机号、身份证号或邮箱。"

    assert after_tool_callback.filter_pii(text, show_logs=False) == text


def test_filter_pii_converts_none_to_empty_string():
    assert after_tool_callback.filter_pii(None, show_logs=False) == ""


def test_filter_pii_logs_detected_values_when_enabled(capsys):
    filtered = after_tool_callback.filter_pii(
        "联系邮箱 bob@example.com",
        patterns={"邮箱": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}"},
        show_logs=True,
    )

    captured = capsys.readouterr()
    assert filtered == "联系邮箱 [邮箱已隐藏]"
    assert "bob@example.com" in captured.out


def test_after_tool_callback_wraps_filtered_response_in_content():
    tool = types.SimpleNamespace(name="write_article")
    response = "作者电话13900139000，邮箱writer@example.com"

    content = after_tool_callback.after_tool_callback(
        tool=tool,
        args={},
        tool_context=None,
        tool_response=response,
    )

    assert len(content.parts) == 1
    assert "13900139000" not in content.parts[0].text
    assert "writer@example.com" not in content.parts[0].text
    assert "[电话号码已隐藏]" in content.parts[0].text
    assert "[邮箱已隐藏]" in content.parts[0].text
