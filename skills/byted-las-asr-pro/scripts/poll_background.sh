#!/bin/bash
# ==============================================================================
# 后台轮询脚本 - 动态间隔 + 自动提取结果
# Usage: scripts/poll_background.sh <task_id> [output_dir]
# ==============================================================================

TASK_ID="$1"
OUTPUT_DIR="${2:-output/${TASK_ID}}"

if [ -z "$TASK_ID" ]; then
  echo "❌ 错误: 请提供 task_id"
  exit 1
fi

# Find project root (skill is in skills/<skill-name>, go up 3 levels)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# 加载环境
if [ -f "${PROJECT_ROOT}/.env" ]; then
  source "${PROJECT_ROOT}/.env"
  export LAS_API_KEY LAS_REGION
fi

# 激活虚拟环境
if [ -d "${PROJECT_ROOT}/.las_venv" ]; then
  source "${PROJECT_ROOT}/.las_venv/bin/activate"
fi

OPERATOR_ID="las_asr_pro"
mkdir -p "${OUTPUT_DIR}"

echo "$(date): Starting background polling for task ${TASK_ID}" >> "${OUTPUT_DIR}/poll.log"

# 轮询计数，用于动态调整间隔
ATTEMPT=0

# Poll until terminal state
while true; do
  ((ATTEMPT++))

  # 动态调整轮询间隔:
  # - 前 5 次: 30秒
  # - 5-10 次: 60秒
  # - 10次之后: 120秒
  if [ $ATTEMPT -le 5 ]; then
    SLEEP=30
  elif [ $ATTEMPT -le 10 ]; then
    SLEEP=60
  else
    SLEEP=120
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

    # Auto-extract outputs per SKILD.md spec
    if [ "$STATUS" = "COMPLETED" ]; then
      echo "$(date): Extracting output files..." >> "${OUTPUT_DIR}/poll.log"

      # Extract full transcript
      cat "${OUTPUT_DIR}/result.json" | jq -r '.data.result.text // empty' > "${OUTPUT_DIR}/transcript.txt"

      # Extract utterances if present
      cat "${OUTPUT_DIR}/result.json" | jq '.data.result.utterances // []' > "${OUTPUT_DIR}/utterances.json"

      # Generate CSV if utterances exist
      HAS_UTTERANCES=$(cat "${OUTPUT_DIR}/result.json" | jq -r 'if .data.result.utterances then "yes" else "no" end')
      if [ "$HAS_UTTERANCES" = "yes" ] && [ "$(cat "${OUTPUT_DIR}/utterances.json" | jq 'length')" -gt 0 ]; then
        cat "${OUTPUT_DIR}/result.json" | jq -r '.data.result.utterances[] |
          "\(.start_time/1000)s-\(.end_time/1000)s,\(.additions.speaker // "-"),\(.text),\(.additions.emotion // "-"),\(.additions.gender // "-")' > "${OUTPUT_DIR}/utterances.csv"
        echo "$(date): Generated utterances.csv with $(cat ${OUTPUT_DIR}/utterances.csv | wc -l) lines" >> "${OUTPUT_DIR}/poll.log"
      fi

      # Get audio info
      DURATION_MS=$(cat "${OUTPUT_DIR}/result.json" | jq -r '.data.audio_info.duration // 0')
      DURATION_MIN=$(echo "scale=1; $DURATION_MS / 1000 / 60" | bc)
      echo "$(date): Completed, audio duration = ${DURATION_MIN} minutes" >> "${OUTPUT_DIR}/poll.log"
    fi

    # Create completion flag
    echo "$STATUS" > "${OUTPUT_DIR}/COMPLETED"
    echo "$(date): Poll completed, final status = ${STATUS}" >> "${OUTPUT_DIR}/poll.log"
    exit 0
  fi

  sleep "$SLEEP"
done
