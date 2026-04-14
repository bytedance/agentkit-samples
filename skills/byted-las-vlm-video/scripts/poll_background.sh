#!/bin/bash
# ==============================================================================
# 后台轮询脚本 - 动态间隔
# Usage: scripts/poll_background.sh <task_id> [output_dir]
# ==============================================================================

TASK_ID="$1"
OUTPUT_DIR="${2:-output/${TASK_ID}}"

if [ -z "$TASK_ID" ]; then
  echo "❌ 错误: 请提供 task_id"
  exit 1
fi

# 加载环境
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

if [ -f "${PROJECT_ROOT}/.env" ]; then
  source "${PROJECT_ROOT}/.env"
  export LAS_API_KEY LAS_REGION
fi

# 激活虚拟环境
if [ -d "${PROJECT_ROOT}/.las_venv" ]; then
  source "${PROJECT_ROOT}/.las_venv/bin/activate"
fi

OPERATOR_ID="las_vlm_video"
mkdir -p "${OUTPUT_DIR}"

echo "$(date): Starting background polling for task ${TASK_ID}" >> "${OUTPUT_DIR}/poll.log"

# 轮询计数，用于动态调整间隔
ATTEMPT=0

# Poll until terminal state
while true; do
  ((ATTEMPT++))

  # 动态调整轮询间隔:
  # - 前 5 次: 60秒
  # - 5-10 次: 120秒
  # - 10次之后: 300秒（视频理解时间更长）
  if [ $ATTEMPT -le 5 ]; then
    SLEEP=60
  elif [ $ATTEMPT -le 10 ]; then
    SLEEP=120
  else
    SLEEP=300
  fi

  # Save full response first, then extract status
  FULL_OUTPUT=$(lasutil poll "${OPERATOR_ID}" "${TASK_ID}")
  echo "$FULL_OUTPUT" > "${OUTPUT_DIR}/last_poll.json"

  # Extract status
  STATUS=$(echo "$FULL_OUTPUT" | python3 -c "
import json
import sys
try:
  data = json.load(sys.stdin)
  print(data['metadata']['task_status'])
except Exception as e:
  print('ERROR')
")

  echo "$(date): Attempt $ATTEMPT, status = ${STATUS}, next poll in ${SLEEP}s" >> "${OUTPUT_DIR}/poll.log"

  if [ "$STATUS" = "COMPLETED" ] || [ "$STATUS" = "FAILED" ] || [ "$STATUS" = "TIMEOUT" ] || [ "$STATUS" = "CANCELED" ]; then
    # Save final result
    echo "$FULL_OUTPUT" > "${OUTPUT_DIR}/result.json"

    # Create completion flag
    echo "$STATUS" > "${OUTPUT_DIR}/COMPLETED"
    echo "$(date): Poll completed, final status = ${STATUS}" >> "${OUTPUT_DIR}/poll.log"
    exit 0
  fi

  sleep "$SLEEP"
done
