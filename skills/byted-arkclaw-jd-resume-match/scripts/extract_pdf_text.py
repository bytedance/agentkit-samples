#!/usr/bin/env python3

from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from jd_resume_match_runtime.pdf_extract import main


if __name__ == "__main__":
    raise SystemExit(main())
