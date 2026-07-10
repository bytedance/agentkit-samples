#!/bin/bash

# ==============================================================================
# byted-arkclaw-local-batch-asr 环境初始化脚本
# Usage: source scripts/env_init.sh
# ==============================================================================

set -e

if [ -n "${ZSH_VERSION:-}" ]; then
  SCRIPT_PATH="${(%):-%N}"
else
  SCRIPT_PATH="${BASH_SOURCE[0]}"
fi

SCRIPT_DIR="$(cd "$(dirname "${SCRIPT_PATH}")" && pwd)"
SKILL_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [ ! -d "${SKILL_ROOT}/.venv" ]; then
  python3 -m venv "${SKILL_ROOT}/.venv"
fi

source "${SKILL_ROOT}/.venv/bin/activate"
python -m pip install -U pip setuptools wheel
python -m pip install funasr modelscope imageio-ffmpeg librosa torch torchaudio

FFMPEG_PATH=$(python -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')
ln -sf "$FFMPEG_PATH" "$(dirname "$(command -v python)")/ffmpeg"

export LOCAL_BATCH_ASR_ROOT="$SKILL_ROOT"
export LOCAL_BATCH_ASR_WORKDIR="${SKILL_ROOT}/output/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$LOCAL_BATCH_ASR_WORKDIR"

echo "✅ byted-arkclaw-local-batch-asr 环境初始化完成"
echo "- skill root: $LOCAL_BATCH_ASR_ROOT"
echo "- workdir: $LOCAL_BATCH_ASR_WORKDIR"
echo "- python: $(command -v python)"
