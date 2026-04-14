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
# VLM 视频高光提取结果

## 任务信息
- **任务 ID**: \`${TASK_ID}\`
- **最终状态**: \`${STATUS}\`
EOF

if [ -n "$ESTIMATED_PRICE" ]; then
cat <<EOF
- **预估计费**: ${ESTIMATED_PRICE} 元
EOF
fi

if [ -f "${OUTPUT_DIR}/result.json" ]; then
cat <<EOF

## 分析结果

请查看完整结果在: \`${OUTPUT_DIR}/\`

EOF
fi

cat <<'EOF'

---

本方式的计费均为预估计费，与实际费用有差距，实际费用以运行后火山产生的账单为准。计费说明请参考 [Volcengine LAS 定价](https://www.volcengine.com/docs/6492/1544808)。
EOF
