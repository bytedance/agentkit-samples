#!/bin/bash

# ==============================================================================
# LAS SDK & Skill 环境初始化与更新脚本
# 用法: source scripts/env_init.sh <operator_id>
# ==============================================================================

OPERATOR_ID=$1

if [ -z "$OPERATOR_ID" ]; then
  echo "❌ 错误: 必须提供 operator_id"
  return 1 2>/dev/null || exit 1
fi

# 1. 虚拟环境隔离
# Find project root dynamically, then check for .las_venv
# skill structure: <project_root>/skills/<skill>/scripts/env_init.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# 优先复用项目根目录的虚拟环境，不存在才创建新的
if [ -d "${PROJECT_ROOT}/.las_venv" ]; then
  source "${PROJECT_ROOT}/.las_venv/bin/activate"
elif [ ! -d ".las_venv" ]; then
  python3 -m venv .las_venv
  source .las_venv/bin/activate
else
  source .las_venv/bin/activate
fi

# 2. 获取远程 manifest
manifest_url="https://las-ai-cn-beijing-online.tos-cn-beijing.volces.com/operator_cards_serving/public/skills/sdk/manifest.json"
manifest=$(curl -sf "$manifest_url" || echo '{}')

# 3. 比较 SDK 版本并自动更新
local_ver=$(lasutil --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "0.0.0")
remote_ver=$(echo "$manifest" | jq -r '.sdk_version // "unknown"')

if [ "$local_ver" = "0.0.0" ] || [ "$local_ver" != "$remote_ver" ]; then
  echo "📦 SDK 更新: $local_ver → $remote_ver，正在安装..."
  pip install --quiet --upgrade https://las-ai-cn-beijing-online.tos-cn-beijing.volces.com/operator_cards_serving/public/skills/sdk/las_sdk-0.2.0-py3-none-any.whl
fi

# 4. 检查当前算子的参数变更
op_changes=$(echo "$manifest" | jq -r ".operators.${OPERATOR_ID}.changes_since // {} | to_entries[] | \"  自 \(.key) 起: \(.value[])\"" 2>/dev/null)
if [ -n "$op_changes" ]; then
  echo "⚠️ 算子 ${OPERATOR_ID} 有参数更新:"
  echo "$op_changes"
  echo "建议使用 find-skills 检索并更新此 skill 到最新版本。"
fi

# 5. 初始化工作目录
export LAS_WORKDIR=$(mktemp -d /tmp/las_work_XXXXXX)
echo "✅ 环境初始化完成，工作目录: $LAS_WORKDIR"
