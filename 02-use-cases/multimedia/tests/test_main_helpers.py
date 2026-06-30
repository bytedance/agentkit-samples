from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "main.py"


def load_module():
    spec = importlib.util.spec_from_file_location("multimedia_main_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_pick_best_image_returns_highest_scored_image():
    module = load_module()
    result = module.pick_best_image(
        {
            "scored_image_list": [
                {
                    "shot_id": "shot-1",
                    "prompt": "prompt",
                    "action": "pan",
                    "reference": "ref",
                    "words": "copy",
                    "images": [
                        {"id": "img-low", "url": "https://low", "score": "0.1"},
                        {"id": "img-high", "url": "https://high", "score": "0.9"},
                    ],
                }
            ]
        }
    )

    assert result == [
        {
            "shot_id": "shot-1",
            "prompt": "prompt",
            "action": "pan",
            "reference": "ref",
            "words": "copy",
            "image": {"id": "img-high", "url": "https://high"},
        }
    ]


def test_pick_best_video_returns_highest_scored_video():
    module = load_module()
    result = module.pick_best_video(
        {
            "scored_video_list": [
                {
                    "shot_id": "shot-1",
                    "prompt": "prompt",
                    "action": "zoom",
                    "reference": "ref",
                    "words": "copy",
                    "videos": [
                        {"id": "video-low", "url": "https://low", "score": "0.3"},
                        {"id": "video-high", "url": "https://high", "score": "0.8"},
                    ],
                }
            ]
        }
    )

    assert result[0]["video"] == {"id": "video-high", "url": "https://high"}


def test_parse_last_sse_text_uses_last_data_event():
    module = load_module()
    first = {"content": {"parts": [{"text": "first"}]}}
    second = {"content": {"parts": [{"text": "second"}]}}
    response_text = "\n".join(
        [
            "event: message",
            f"data: {json.dumps(first)}",
            "",
            f"data: {json.dumps(second)}",
        ]
    )

    assert module.parse_last_sse_text(response_text) == "second"


def test_parse_last_sse_text_returns_none_without_data_line():
    module = load_module()

    assert module.parse_last_sse_text("event: ping\n\n") is None


def test_parse_last_sse_text_raises_for_malformed_event_shape():
    module = load_module()

    with pytest.raises(KeyError):
        module.parse_last_sse_text('data: {"content": {}}')
