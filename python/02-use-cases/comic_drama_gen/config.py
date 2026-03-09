import os
from pathlib import Path

BASE_URL = "http://localhost:8000"
APP = "comic_drama_gen"
PROJECT_ROOT = Path(__file__).parent.resolve()
LOG_DIR = Path("/tmp/comic_drama_tests")


def _resolve_outputs_dir() -> Path:
    """优先读取 .env 中的 COMIC_DRAMA_OUTPUT_DIR，确保与 Agent 输出目录一致。"""
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                if key.strip() == "COMIC_DRAMA_OUTPUT_DIR":
                    p = Path(value.strip().strip("'\""))
                    return p if p.is_absolute() else PROJECT_ROOT / p
    return PROJECT_ROOT / "outputs"


OUTPUTS_DIR = _resolve_outputs_dir()

ENV_BASE = {
    "VOLCENGINE_ACCESS_KEY": os.getenv("VOLCENGINE_ACCESS_KEY", ""),
    "VOLCENGINE_SECRET_KEY": os.getenv("VOLCENGINE_SECRET_KEY", ""),
    "MODEL_AGENT_API_KEY": os.getenv(
        "MODEL_AGENT_API_KEY", os.getenv("ARK_API_KEY", "")
    ),
    "DATABASE_TOS_BUCKET": os.getenv("DATABASE_TOS_BUCKET", ""),
}


def load_env():
    """Load variables from .env file into a dictionary."""
    env_dict = {}
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip().lstrip("export ").strip()
                    value = value.strip().strip("'\"")
                    if key:
                        env_dict[key] = value
    return env_dict
