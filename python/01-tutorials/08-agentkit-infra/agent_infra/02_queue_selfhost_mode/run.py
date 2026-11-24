"""Queue SelfHosted：通过 APIG 对话，通过自建 Dispatcher 执行工具。"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.sample import main  # noqa: E402

if __name__ == "__main__":
    main("queue-selfhost")
