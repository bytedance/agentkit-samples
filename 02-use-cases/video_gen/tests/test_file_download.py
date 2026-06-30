from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "tool" / "file_download.py"


class FakeResponse:
    def __init__(self, chunks):
        self.chunks = chunks

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        return iter(self.chunks)


def load_module():
    spec = importlib.util.spec_from_file_location("video_file_download", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_file_download_requires_url_list():
    module = load_module()

    with pytest.raises(ValueError, match="url parameter must be a list"):
        module.file_download("https://example.com/file.txt")


def test_file_download_requires_filename_list_length_to_match():
    module = load_module()

    with pytest.raises(ValueError, match="filename list length"):
        module.file_download(
            ["https://example.com/a.txt", "https://example.com/b.txt"],
            filename=["a.txt"],
        )


def test_download_single_file_uses_url_filename(monkeypatch, tmp_path):
    module = load_module()
    monkeypatch.setattr(
        module.requests,
        "get",
        lambda *args, **kwargs: FakeResponse([b"hello", b"", b" world"]),
    )

    path = module._download_single_file(
        "https://example.com/folder/report%20final.txt",
        save_dir=str(tmp_path),
    )

    assert Path(path).name == "report final.txt"
    assert Path(path).read_bytes() == b"hello world"


def test_download_single_file_avoids_overwrite(monkeypatch, tmp_path):
    module = load_module()
    existing = tmp_path / "report.txt"
    existing.write_text("old", encoding="utf-8")
    monkeypatch.setattr(module.requests, "get", lambda *args, **kwargs: FakeResponse([b"new"]))

    path = module._download_single_file(
        "https://example.com/report.txt",
        save_dir=str(tmp_path),
    )

    assert Path(path).name == "report_1.txt"
    assert existing.read_text(encoding="utf-8") == "old"
    assert Path(path).read_bytes() == b"new"
