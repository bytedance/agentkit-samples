#!/bin/bash

# ==============================================================================
# byted-arkclaw-call-records-simulate 环境初始化脚本
# 用法:
#   方式 A（推荐，确保在 skill 根目录执行）:
#       cd path/to/byted-arkclaw-call-records-simulate && source scripts/env_init.sh
#   方式 B:
#       source path/to/byted-arkclaw-call-records-simulate/scripts/env_init.sh
# ==============================================================================

# 兼容性地解析脚本自身目录：
# 优先使用 BASH_SOURCE，退化到 $0，最后退到当前目录。
_src="${BASH_SOURCE[0]:-$0}"
if [ -z "$_src" ] || [ "$_src" = "bash" ] || [ "$_src" = "-bash" ]; then
  # 被 source 且拿不到路径时，假定 PWD 即为 skill 根目录
  SKILL_ROOT="$(pwd)"
else
  SCRIPT_DIR="$(cd "$(dirname "$_src")" && pwd)"
  SKILL_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
fi

# 如果解析出来的 SKILL_ROOT 里没有 SKILL.md，则回退到 PWD
if [ ! -f "${SKILL_ROOT}/SKILL.md" ] && [ -f "$(pwd)/SKILL.md" ]; then
  SKILL_ROOT="$(pwd)"
fi

echo "📁 SKILL_ROOT=${SKILL_ROOT}"

# 1. 创建/复用虚拟环境
if [ ! -d "${SKILL_ROOT}/tts_env" ]; then
  echo "📦 首次初始化，创建虚拟环境 ${SKILL_ROOT}/tts_env ..."
  python3 -m venv "${SKILL_ROOT}/tts_env"
fi

# 2. 激活虚拟环境
# shellcheck disable=SC1091
source "${SKILL_ROOT}/tts_env/bin/activate"

# 3. 校验/安装依赖
if ! python -c "import edge_tts" >/dev/null 2>&1; then
  echo "📦 安装 edge-tts ..."
  pip install --quiet --upgrade pip
  pip install --quiet edge-tts
fi

# 4. 导出工作目录 & 准备目录
export CALL_SIM_WORKDIR="${SKILL_ROOT}"
mkdir -p "${SKILL_ROOT}/materials" "${SKILL_ROOT}/output"

echo "✅ 环境就绪: CALL_SIM_WORKDIR=${CALL_SIM_WORKDIR}"
echo "   - Python: $(python --version)"
echo "   - edge-tts: $(python -c 'import edge_tts, sys; print(edge_tts.__version__)' 2>/dev/null || echo 'installed')"
