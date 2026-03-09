"""
任务目录管理工具
- 为每个漫剧生成任务创建独立的文件夹
- 输出目录由环境变量 COMIC_DRAMA_OUTPUT_DIR 控制（默认为 comic_drama_gen 目录下的 output/）
- 自动 FIFO 清理，最多保留 16 个任务
- 目录结构:
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

用法:
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

# 以 comic_drama_gen 目录为基准目录
# 路径关系: scripts/ -> comic-drama-master/ -> skill/ -> comic_drama_gen/
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _resolve_outputs_dir() -> Path:
    """
    解析产物输出目录：
    - 优先读取环境变量 COMIC_DRAMA_OUTPUT_DIR
      - 绝对路径：直接使用
      - 相对路径：基于 comic_drama_gen 目录解析
    - 默认为 comic_drama_gen 目录下的 output/
    """
    env_val = os.environ.get("COMIC_DRAMA_OUTPUT_DIR", "").strip()
    if env_val:
        p = Path(env_val)
        if p.is_absolute():
            return p
        # 相对路径基于 comic_drama_gen 目录解析（而非 cwd）
        return _PROJECT_ROOT / p
    return _PROJECT_ROOT / "output"


def _get_outputs_dir() -> Path:
    """每次调用时重新解析目录，支持运行时修改环境变量。"""
    outputs_dir = _resolve_outputs_dir()
    outputs_dir.mkdir(parents=True, exist_ok=True)
    return outputs_dir


def _sanitize_name(name: str) -> str:
    """保留中文/英文/数字/连字符，去除其他符号，截断至 20 字符"""
    sanitized = re.sub(r"[^\w\u4e00-\u9fff\-]", "_", name)[:20]
    return sanitized.strip("_") or "task"


def _cleanup_old_tasks(outputs_dir: Path, max_tasks: int = _MAX_TASKS) -> List[str]:
    """FIFO 清理：超出限额时删除最旧的任务目录。"""
    task_dirs = sorted(
        [d for d in outputs_dir.iterdir() if d.is_dir()],
        key=lambda d: d.stat().st_ctime,
    )
    deleted = []
    while len(task_dirs) >= max_tasks:
        oldest = task_dirs.pop(0)
        shutil.rmtree(oldest, ignore_errors=True)
        deleted.append(oldest.name)
        logger.info(f"[task_manager] FIFO 删除旧任务: {oldest.name}")
    return deleted


def init_task(task_name: str) -> Dict:
    """
    初始化任务目录，执行 FIFO 清理后创建新任务文件夹。

    Args:
        task_name: 任务名称（如"韩立大战极阴老祖"）

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
        f"[task_manager] 任务目录初始化完成: {folder_name} (输出目录: {outputs_dir})"
    )
    return result


def save_task_document(task_folder: str, doc_name: str, content: str) -> str:
    """
    保存文本文档（Markdown）到任务目录。

    Args:
        task_folder: 任务根目录绝对路径（来自 init_task 返回值）
        doc_name:    文件名，如 "requirements.md" / "plot.md" / "script.md" / "characters.md"
        content:     文件内容（Markdown 格式字符串）

    Returns:
        str: 保存成功的文件绝对路径
    """
    folder = Path(task_folder)
    folder.mkdir(parents=True, exist_ok=True)
    file_path = folder / doc_name
    file_path.write_text(content, encoding="utf-8")
    logger.info(f"[task_manager] 文档已保存: {file_path}")
    return str(file_path.absolute())


def list_tasks() -> List[Dict]:
    """列出所有任务目录，按创建时间倒序。"""
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
        print("用法:")
        print('  python scripts/task_manager.py init "<task_name>"')
        print(
            '  python scripts/task_manager.py save "<task_folder>" "<doc_name>" "<content>"'
        )
        print("  python scripts/task_manager.py list")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "init":
        if len(sys.argv) < 3:
            print("错误: 缺少 task_name 参数")
            sys.exit(1)
        result = init_task(sys.argv[2])
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "save":
        if len(sys.argv) < 5:
            print(
                "错误: 用法: python scripts/task_manager.py save <task_folder> <doc_name> <content>"
            )
            sys.exit(1)
        path = save_task_document(sys.argv[2], sys.argv[3], sys.argv[4])
        print(json.dumps({"saved": path}, ensure_ascii=False))

    elif cmd == "list":
        tasks = list_tasks()
        print(json.dumps(tasks, ensure_ascii=False, indent=2))

    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)
