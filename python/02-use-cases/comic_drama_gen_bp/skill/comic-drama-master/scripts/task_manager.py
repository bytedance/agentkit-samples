"""
Task directory management tool
- Creates a dedicated folder for each comic drama generation task
- The output directory is controlled by the COMIC_DRAMA_OUTPUT_DIR environment variable (defaults to output/ under the comic_drama_gen directory)
- Automatic FIFO cleanup, keeping at most 16 tasks
- Directory structure:
    {COMIC_DRAMA_OUTPUT_DIR}/
    └── task_{timestamp}_{name}/
        ├── requirements.md
        ├── plot.md
        ├── script.md
        ├── characters.md
        ├── cover.jpg
        ├── storyboard/
        ├── characters/
        ├── videos/
        └── final/

Usage:
    python scripts/task_manager.py init "<task_name>"
    python scripts/task_manager.py save "<task_folder>" "<doc_name>" "<content>"
    python scripts/task_manager.py list
"""

import json
import logging
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

_MAX_TASKS = 16

# Use the comic_drama_gen directory as the base directory
# Path relationship: scripts/ -> comic-drama-master/ -> skill/ -> comic_drama_gen/
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _resolve_outputs_dir() -> Path:
    """
    Resolve the artifact output directory:
    - The COMIC_DRAMA_OUTPUT_DIR environment variable takes precedence
      - Absolute path: used as-is
      - Relative path: resolved relative to the comic_drama_gen directory
    - Defaults to output/ under the comic_drama_gen directory
    """
    env_val = os.environ.get("COMIC_DRAMA_OUTPUT_DIR", "").strip()
    if env_val:
        p = Path(env_val)
        if p.is_absolute():
            return p
        # Relative paths are resolved against the comic_drama_gen directory (not cwd)
        return _PROJECT_ROOT / p
    return _PROJECT_ROOT / "output"


def _get_outputs_dir() -> Path:
    """Re-resolve the directory on every call, so the environment variable can be changed at runtime."""
    outputs_dir = _resolve_outputs_dir()
    outputs_dir.mkdir(parents=True, exist_ok=True)
    return outputs_dir


def _sanitize_name(name: str) -> str:
    """Keep Chinese/English/digits/hyphens, strip other symbols, truncate to 20 characters"""
    sanitized = re.sub(r"[^\w\u4e00-\u9fff\-]", "_", name)[:20]
    return sanitized.strip("_") or "task"


def _cleanup_old_tasks(outputs_dir: Path, max_tasks: int = _MAX_TASKS) -> List[str]:
    """FIFO cleanup: delete the oldest task directories when over the limit."""
    task_dirs = sorted(
        [d for d in outputs_dir.iterdir() if d.is_dir()],
        key=lambda d: d.stat().st_ctime,
    )
    deleted = []
    while len(task_dirs) >= max_tasks:
        oldest = task_dirs.pop(0)
        shutil.rmtree(oldest, ignore_errors=True)
        deleted.append(oldest.name)
        logger.info(f"[task_manager] FIFO deleted old task: {oldest.name}")
    return deleted


def init_task(task_name: str) -> Dict:
    """
    Initialize the task directory, creating a new task folder after FIFO cleanup.

    Args:
        task_name: Task name (e.g. "Han Li Battles the Ji Yin Patriarch")

    Returns:
        dict: task_id, task_folder, storyboard_dir, characters_dir, videos_dir, final_dir, deleted_tasks
    """
    outputs_dir = _get_outputs_dir()
    deleted = _cleanup_old_tasks(outputs_dir)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sanitized = _sanitize_name(task_name)
    task_id = f"task_{timestamp}"
    folder_name = f"{task_id}_{sanitized}"
    task_folder = outputs_dir / folder_name

    storyboard_dir = task_folder / "storyboard"
    characters_dir = task_folder / "characters"
    videos_dir = task_folder / "videos"
    final_dir = task_folder / "final"

    for d in [task_folder, storyboard_dir, characters_dir, videos_dir, final_dir]:
        d.mkdir(parents=True, exist_ok=True)

    result = {
        "task_id": task_id,
        "task_folder": str(task_folder.absolute()),
        "storyboard_dir": str(storyboard_dir.absolute()),
        "characters_dir": str(characters_dir.absolute()),
        "videos_dir": str(videos_dir.absolute()),
        "final_dir": str(final_dir.absolute()),
        "outputs_dir": str(outputs_dir.absolute()),
        "deleted_tasks": deleted,
    }
    logger.info(
        f"[task_manager] Task directory initialized: {folder_name} (output directory: {outputs_dir})"
    )
    return result


def save_task_document(task_folder: str, doc_name: str, content: str) -> str:
    """
    Save a text document (Markdown) to the task directory.

    Args:
        task_folder: Absolute path to the task root directory (from the init_task return value)
        doc_name:    File name, e.g. "requirements.md" / "plot.md" / "script.md" / "characters.md"
        content:     File content (Markdown-formatted string)

    Returns:
        str: Absolute path of the saved file
    """
    folder = Path(task_folder)
    folder.mkdir(parents=True, exist_ok=True)
    file_path = folder / doc_name
    file_path.write_text(content, encoding="utf-8")
    logger.info(f"[task_manager] Document saved: {file_path}")
    return str(file_path.absolute())


def list_tasks() -> List[Dict]:
    """List all task directories, sorted by creation time in descending order."""
    outputs_dir = _get_outputs_dir()
    tasks = []
    for d in sorted(
        [x for x in outputs_dir.iterdir() if x.is_dir()],
        key=lambda x: x.stat().st_ctime,
        reverse=True,
    ):
        files = [str(f.relative_to(d)) for f in d.rglob("*") if f.is_file()]
        tasks.append(
            {
                "task_folder": str(d.absolute()),
                "name": d.name,
                "created_at": datetime.fromtimestamp(d.stat().st_ctime).isoformat(),
                "file_count": len(files),
                "files": files[:20],
            }
        )
    return tasks


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print('  python scripts/task_manager.py init "<task_name>"')
        print(
            '  python scripts/task_manager.py save "<task_folder>" "<doc_name>" "<content>"'
        )
        print("  python scripts/task_manager.py list")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "init":
        if len(sys.argv) < 3:
            print("Error: missing task_name argument")
            sys.exit(1)
        result = init_task(sys.argv[2])
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "save":
        if len(sys.argv) < 5:
            print(
                "Error: usage: python scripts/task_manager.py save <task_folder> <doc_name> <content>"
            )
            sys.exit(1)
        path = save_task_document(sys.argv[2], sys.argv[3], sys.argv[4])
        print(json.dumps({"saved": path}, ensure_ascii=False))

    elif cmd == "list":
        tasks = list_tasks()
        print(json.dumps(tasks, ensure_ascii=False, indent=2))

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
