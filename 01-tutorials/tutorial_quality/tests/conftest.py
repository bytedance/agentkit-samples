from __future__ import annotations

import sys
from pathlib import Path


TUTORIAL_ROOT = Path(__file__).resolve().parents[2]

if str(TUTORIAL_ROOT) not in sys.path:
    sys.path.insert(0, str(TUTORIAL_ROOT))
