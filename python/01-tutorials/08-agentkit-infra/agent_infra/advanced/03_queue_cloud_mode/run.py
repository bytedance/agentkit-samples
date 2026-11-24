"""Queue Cloud 进阶模式：通过 APIG 对话，由平台调度云沙箱。"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from common.sample import main  # noqa: E402

if __name__ == "__main__":
    main("queue-cloud")
