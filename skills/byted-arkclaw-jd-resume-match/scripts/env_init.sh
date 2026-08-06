#!/bin/bash

set -e

if [ -n "${ZSH_VERSION:-}" ]; then
  SCRIPT_PATH="${(%):-%N}"
else
  SCRIPT_PATH="${BASH_SOURCE[0]}"
fi

SCRIPT_DIR="$(cd "$(dirname "${SCRIPT_PATH}")" && pwd)"
SKILL_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ROOT_VENV="$(cd "${SKILL_ROOT}/.." && pwd)/.venv"

reuse_venv() {
  local path="$1"
  if [ -d "$path" ] && [ -x "$path/bin/python" ]; then
    source "$path/bin/activate"
    if python - <<'PY' >/dev/null 2>&1
import importlib.util
mods = ["pypdf", "fitz", "yaml"]
raise SystemExit(0 if all(importlib.util.find_spec(m) for m in mods) else 1)
PY
    then
      return 0
    fi
  fi
  return 1
}

if ! reuse_venv "$ROOT_VENV"; then
  if [ ! -d "${SKILL_ROOT}/.venv" ]; then
    python3 -m venv "${SKILL_ROOT}/.venv"
  fi
  source "${SKILL_ROOT}/.venv/bin/activate"
  python -m pip install -U pip setuptools wheel
  python -m pip install pypdf pymupdf pyyaml pillow
fi

export JD_RESUME_MATCH_ROOT="$SKILL_ROOT"
mkdir -p "$SKILL_ROOT/output"

echo "✅ byted-arkclaw-jd-resume-match 环境初始化完成"
echo "- skill root: $JD_RESUME_MATCH_ROOT"
echo "- python: $(command -v python)"
if command -v tesseract >/dev/null 2>&1; then
  echo "- OCR fallback: tesseract 可用"
else
  echo "- OCR fallback: 未检测到 tesseract，仅保证可提取可复制文本 PDF"
fi
