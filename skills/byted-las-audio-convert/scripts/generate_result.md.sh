#!/bin/bash
# ==============================================================================
# 生成结果展示 markdown 模板，自动包含计费声明
# Usage: scripts/generate_result.md.sh <result_json> <estimated_price>
# ==============================================================================

RESULT_JSON="$1"
ESTIMATED_PRICE="$2"

if [ -z "$RESULT_JSON" ] || [ ! -f "$RESULT_JSON" ]; then
  echo "❌ 错误: 需要提供 result.json 文件路径"
  exit 1
fi

cat <<EOF
# 音频转换结果

## 任务信息
- **算子**: \`las_audio_convert\`
EOF

if [ -n "$ESTIMATED_PRICE" ]; then
cat <<EOF
- **预估计费**: ${ESTIMATED_PRICE} 元
EOF
fi

cat <<EOF

## 转换结果

| 输入 | 输出路径 | 时长 | 状态 |
|------|---------|------|------|
EOF

# Extract and print each row
cat "$RESULT_JSON" | jq -r '.data.audios[] |
  "| \(.input_path | split("/") | last) | \(.output_path) | \(.duration) | '"\$"' .status |'
EOF

cat <<'EOF'

---

本方式的计费均为预估计费，与实际费用有差距，实际费用以运行后火山产生的账单为准。计费说明请参考 [Volcengine LAS 定价](https://www.volcengine.com/docs/6492/1544808)。
EOF
