"""Direct：通过 Harness App 创建会话并运行 SSE。"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.sample import main  # noqa: E402

if __name__ == "__main__":
    main("direct")
