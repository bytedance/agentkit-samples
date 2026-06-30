from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "tools" / "image" / "image_cropper.py"
)


def load_module(monkeypatch):
    tools = types.ModuleType("tools")
    tos_upload = types.ModuleType("tools.tos_upload")
    tos_upload.upload_file_to_tos = lambda path: f"tos://{path}"
    monkeypatch.setitem(sys.modules, "tools", tools)
    monkeypatch.setitem(sys.modules, "tools.tos_upload", tos_upload)

    spec = importlib.util.spec_from_file_location("inspection_image_cropper", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("<bbox>163 494 738 864</bbox>", (163, 494, 738, 864)),
        (" <bbox>163,494,738,864</bbox> ", (163, 494, 738, 864)),
        ("<bbox>738 864 163 494</bbox>", (163, 494, 738, 864)),
        ("<bbox>0 0 1000 1000</bbox>", (0, 0, 1000, 1000)),
    ],
)
def test_parse_bbox_accepts_supported_formats(monkeypatch, raw, expected):
    module = load_module(monkeypatch)

    assert module.parse_bbox(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "163 494 738 864",
        "<bbox>163 494 738</bbox>",
        "<bbox>x y z q</bbox>",
        "<box>163 494 738 864</box>",
    ],
)
def test_parse_bbox_rejects_invalid_format(monkeypatch, raw):
    module = load_module(monkeypatch)

    with pytest.raises(ValueError, match="无法解析bbox格式"):
        module.parse_bbox(raw)
