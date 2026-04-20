#!/usr/bin/env python3
"""
Incrementally sync local resources from remote TOS objects.

Flow:
- Read remote version from /viking-developer/version
- Compare with ./resources/version
- If changed, fetch /viking-developer/meta.json and diff with ./resources/meta.json
- Download changed files, delete removed files, then update local meta/version
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Dict
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import urlopen


REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET_DIR = REPO_ROOT / "resources"

BASE_URL = "http://viking-skills.tos-cn-beijing.volces.com/viking-developer"
VERSION_URL = f"{BASE_URL}/version"
META_URL = f"{BASE_URL}/meta.json"
LOCAL_VERSION_PATH = TARGET_DIR / "version"
LOCAL_META_PATH = TARGET_DIR / "meta.json"
REQUEST_TIMEOUT_SECONDS = 30


def _fetch_bytes(url: str) -> bytes:
    try:
        with urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return response.read()
    except HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} while fetching {url}") from exc
    except URLError as exc:
        raise RuntimeError(f"failed to fetch {url}: {exc.reason}") from exc


def _fetch_text(url: str) -> str:
    return _fetch_bytes(url).decode("utf-8")


def _fetch_json(url: str) -> tuple[Dict[str, Any], str]:
    raw_text = _fetch_text(url)
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid json from {url}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"invalid json from {url}: expected an object")
    return data, raw_text


def _read_text_if_exists(file_path: Path) -> str:
    if not file_path.exists():
        return ""
    return file_path.read_text(encoding="utf-8")


def _load_local_meta(file_path: Path) -> Dict[str, Any]:
    if not file_path.exists():
        return {}

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"warning: invalid local meta ignored: {file_path}: {exc}", file=sys.stderr)
        return {}

    if not isinstance(data, dict):
        print(f"warning: invalid local meta ignored: {file_path}", file=sys.stderr)
        return {}
    return data


def _build_meta_map(meta: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    files = meta.get("files")
    if not isinstance(files, list):
        return {}

    result: Dict[str, Dict[str, Any]] = {}
    for item in files:
        if not isinstance(item, dict):
            continue
        rel_path = item.get("path")
        if not isinstance(rel_path, str) or not rel_path:
            continue
        result[rel_path] = item
    return result


def _resolve_resource_path(relative_path: str) -> Path:
    posix_path = PurePosixPath(relative_path)
    if posix_path.is_absolute() or ".." in posix_path.parts:
        raise RuntimeError(f"invalid relative path in meta.json: {relative_path}")
    return TARGET_DIR.joinpath(*posix_path.parts)


def _remote_file_url(relative_path: str) -> str:
    return f"{BASE_URL}/{quote(relative_path, safe='/')}"


def _should_download(
    remote_entry: Dict[str, Any], local_entry: Dict[str, Any] | None, local_path: Path
) -> bool:
    if local_entry is None:
        return True
    if local_entry.get("md5") != remote_entry.get("md5"):
        return True
    if local_entry.get("size") != remote_entry.get("size"):
        return True
    if not local_path.exists() or not local_path.is_file():
        return True

    remote_size = remote_entry.get("size")
    if isinstance(remote_size, int) and local_path.stat().st_size != remote_size:
        return True
    return False


def _download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            with tempfile.NamedTemporaryFile(delete=False, dir=destination.parent) as tmp:
                shutil.copyfileobj(response, tmp)
                temp_path = Path(tmp.name)
        temp_path.replace(destination)
    except HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} while downloading {url}") from exc
    except URLError as exc:
        raise RuntimeError(f"failed to download {url}: {exc.reason}") from exc
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def _prune_empty_dirs(start_dir: Path) -> None:
    current = start_dir
    while current != TARGET_DIR and current.exists():
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent


def _delete_file(file_path: Path) -> None:
    if file_path.exists():
        file_path.unlink()
        _prune_empty_dirs(file_path.parent)


def _write_text(file_path: Path, content: str) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


def main() -> int:
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    remote_version = _fetch_text(VERSION_URL).strip()
    if not remote_version:
        print(f"remote version is empty: {VERSION_URL}", file=sys.stderr)
        return 1

    local_version = _read_text_if_exists(LOCAL_VERSION_PATH).strip()
    if local_version == remote_version:
        print("resources are already up to date")
        return 0

    remote_meta, remote_meta_raw = _fetch_json(META_URL)
    if not isinstance(remote_meta.get("files"), list):
        print(f"invalid remote meta format: {META_URL}", file=sys.stderr)
        return 1
    local_meta = _load_local_meta(LOCAL_META_PATH)

    remote_files = _build_meta_map(remote_meta)
    local_files = _build_meta_map(local_meta)

    downloaded = 0
    deleted = 0

    for relative_path, remote_entry in sorted(remote_files.items()):
        local_path = _resolve_resource_path(relative_path)
        local_entry = local_files.get(relative_path)
        if not _should_download(remote_entry, local_entry, local_path):
            continue

        file_url = _remote_file_url(relative_path)
        _download_file(file_url, local_path)
        downloaded += 1
        print(f"UPDATED: {relative_path}")

    for relative_path in sorted(local_files.keys() - remote_files.keys(), reverse=True):
        local_path = _resolve_resource_path(relative_path)
        _delete_file(local_path)
        deleted += 1
        print(f"DELETED: {relative_path}")

    _write_text(LOCAL_META_PATH, remote_meta_raw)
    _write_text(LOCAL_VERSION_PATH, remote_version + "\n")

    print(f"sync done: downloaded={downloaded}, deleted={deleted}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
