"""Small .env loader for standalone skill scripts."""

import os
from pathlib import Path


def load_project_env() -> None:
    """Load comic_drama_gen/.env without overriding exported variables."""
    project_root = Path(__file__).resolve().parents[3]
    env_file = project_root / ".env"
    if not env_file.exists():
        return

    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export ") :].strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
