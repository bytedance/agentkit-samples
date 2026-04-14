#!/bin/bash
# ==============================================================================
# 生成结果展示 markdown 模板，自动包含计费声明
# Usage: scripts/generate_result.md.sh <task_id> <output_dir> <estimated_price>
# ==============================================================================

TASK_ID="$1"
OUTPUT_DIR="$2"
ESTIMATED_PRICE="$3"

if [ -z "$TASK_ID" ] || [ -z "$OUTPUT_DIR" ]; then
  echo "❌ 错误: 参数不全"
  exit 1
fi

STATUS=$(cat "${OUTPUT_DIR}/COMPLETED" 2>/dev/null || echo "UNKNOWN")

cat <<EOF
# ASR 识别结果

## 任务信息
- **任务 ID**: \`${TASK_ID}\`
- **最终状态**: \`${STATUS}\`
EOF

if [ -n "$ESTIMATED_PRICE" ]; then
cat <<EOF
- **预估计费**: ${ESTIMATED_PRICE} 元
EOF
fi

if [ -f "${OUTPUT_DIR}/transcript.txt" ]; then
  TEXT_LEN=$(wc -c < "${OUTPUT_DIR}/transcript.txt")
  DURATION_MS=$(cat "${OUTPUT_DIR}/result.json" | jq -r '.data.audio_info.duration // 0')
  DURATION_MIN=$(echo "scale=1; $DURATION_MS / 1000 / 60" | bc)
  LANG=$(cat "${OUTPUT_DIR}/result.json" | jq -r '.data.result.additions.lid_lang // "unknown"')

cat <<EOF

## 识别统计
- **音频时长**: ${DURATION_MIN} 分钟
- **识别语种**: ${LANG}
- **总字数**: ${TEXT_LEN} 字符

## 文本预览（前 500 字）

\`\`\`
$(head -c 500 "${OUTPUT_DIR}/transcript.txt")
\`\`\`
EOF
fi

cat <<EOF

## 结果文件位置
\`${OUTPUT_DIR}/\`
- \`result.json\` - 完整 API 响应
- \`transcript.txt\` - 完整识别文本
EOF

if [ -f "${OUTPUT_DIR}/utterances.csv" ]; then
cat <<EOF
- \`utterances.csv\` - 分句说话人信息（CSV格式）
- \`utterances.json\` - 分句原始数据
EOF
fi

cat <<'EOF'

---

本方式的计费均为预估计费，与实际费用有差距，实际费用以运行后火山产生的账单为准。计费说明请参考 [Volcengine LAS 定价](https://www.volcengine.com/docs/6492/1544808)。
EOF
